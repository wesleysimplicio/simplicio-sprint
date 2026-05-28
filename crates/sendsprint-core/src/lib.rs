//! Sprint-plan validator exposed to Python via PyO3.
//!
//! The Python caller hands us JSON-serialised sprint data (already produced by
//! `orjson`) and we return a structured report. We do not call back into
//! Python from any hot loop, so the GIL is released for the entire validation
//! step.

use std::collections::{HashMap, HashSet};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use serde::Deserialize;

const VALID_STATUSES: &[&str] = &[
    "todo", "to do", "open", "ready", "backlog",
    "doing", "in progress", "in review", "review", "active", "started",
    "done", "closed", "resolved", "completed",
    "blocked", "on hold",
    "em andamento", "em revisão", "em revisao", "fechado", "concluído", "concluida",
    "en progreso", "cerrado", "terminado",
];

#[derive(Debug, Deserialize)]
struct SprintInput {
    #[serde(default)]
    id: String,
    #[serde(default)]
    name: String,
    #[serde(default)]
    items: Vec<SprintItemInput>,
}

#[derive(Debug, Deserialize)]
struct SprintItemInput {
    #[serde(default)]
    id: String,
    key: String,
    #[serde(rename = "type", default)]
    item_type: String,
    #[serde(default)]
    status: String,
    #[serde(default)]
    parent_key: Option<String>,
    #[serde(default)]
    story_points: Option<f64>,
    #[serde(default)]
    labels: Vec<String>,
    #[serde(default)]
    links: Vec<LinkInput>,
    #[serde(default)]
    acceptance_criteria: Option<String>,
}

#[derive(Debug, Deserialize)]
struct LinkInput {
    #[serde(rename = "type", default)]
    link_type: String,
    target_key: String,
}

#[derive(Debug)]
struct Finding {
    severity: &'static str,
    code: &'static str,
    item_key: Option<String>,
    message: String,
}

fn validate(sprint: &SprintInput) -> Vec<Finding> {
    let mut findings = Vec::new();
    let n = sprint.items.len();

    let mut by_key: HashMap<&str, &SprintItemInput> = HashMap::with_capacity(n);
    let mut duplicates: HashSet<&str> = HashSet::new();

    for item in &sprint.items {
        if item.key.is_empty() {
            findings.push(Finding {
                severity: "error",
                code: "missing_key",
                item_key: None,
                message: format!("item with id={:?} has empty key", item.id),
            });
            continue;
        }
        if by_key.insert(item.key.as_str(), item).is_some() {
            duplicates.insert(item.key.as_str());
        }
    }

    for key in &duplicates {
        findings.push(Finding {
            severity: "error",
            code: "duplicate_key",
            item_key: Some((*key).to_string()),
            message: format!("duplicate item key: {}", key),
        });
    }

    let valid_status: HashSet<&str> = VALID_STATUSES.iter().copied().collect();

    for item in &sprint.items {
        if item.key.is_empty() {
            continue;
        }

        if let Some(parent) = item.parent_key.as_deref() {
            if parent == item.key {
                findings.push(Finding {
                    severity: "error",
                    code: "self_parent",
                    item_key: Some(item.key.clone()),
                    message: format!("item {} is its own parent", item.key),
                });
            } else if !by_key.contains_key(parent) {
                findings.push(Finding {
                    severity: "warning",
                    code: "orphan_parent",
                    item_key: Some(item.key.clone()),
                    message: format!("parent_key {} not present in sprint", parent),
                });
            }
        }

        if let Some(points) = item.story_points {
            if points < 0.0 || !points.is_finite() {
                findings.push(Finding {
                    severity: "error",
                    code: "invalid_story_points",
                    item_key: Some(item.key.clone()),
                    message: format!("story_points {} must be a non-negative number", points),
                });
            }
        }

        if !item.status.is_empty() {
            let normalized = item.status.to_lowercase();
            if !valid_status.contains(normalized.as_str()) {
                findings.push(Finding {
                    severity: "warning",
                    code: "unknown_status",
                    item_key: Some(item.key.clone()),
                    message: format!("unrecognized status: {}", item.status),
                });
            }
        }

        for link in &item.links {
            if link.target_key.is_empty() {
                findings.push(Finding {
                    severity: "warning",
                    code: "empty_link_target",
                    item_key: Some(item.key.clone()),
                    message: format!("link type={} has empty target_key", link.link_type),
                });
            } else if !by_key.contains_key(link.target_key.as_str())
                && link.target_key != item.key
            {
                findings.push(Finding {
                    severity: "info",
                    code: "external_link",
                    item_key: Some(item.key.clone()),
                    message: format!("link target {} not in this sprint", link.target_key),
                });
            }
        }

        if item.item_type == "Story"
            && item
                .acceptance_criteria
                .as_deref()
                .map(|s| s.trim().is_empty())
                .unwrap_or(true)
        {
            findings.push(Finding {
                severity: "warning",
                code: "missing_acceptance_criteria",
                item_key: Some(item.key.clone()),
                message: format!("Story {} has no acceptance_criteria", item.key),
            });
        }

        let mut label_seen: HashSet<&str> = HashSet::with_capacity(item.labels.len());
        for label in &item.labels {
            if !label_seen.insert(label.as_str()) {
                findings.push(Finding {
                    severity: "info",
                    code: "duplicate_label",
                    item_key: Some(item.key.clone()),
                    message: format!("duplicate label on {}: {}", item.key, label),
                });
            }
        }
    }

    detect_cycles(&sprint.items, &by_key, &mut findings);

    findings
}

fn detect_cycles(
    items: &[SprintItemInput],
    by_key: &HashMap<&str, &SprintItemInput>,
    findings: &mut Vec<Finding>,
) {
    #[derive(Copy, Clone, PartialEq, Eq)]
    enum Mark {
        Unvisited,
        Visiting,
        Done,
    }

    let mut state: HashMap<&str, Mark> = items
        .iter()
        .filter(|i| !i.key.is_empty())
        .map(|i| (i.key.as_str(), Mark::Unvisited))
        .collect();

    let mut reported: HashSet<String> = HashSet::new();

    for start_item in items {
        if start_item.key.is_empty() {
            continue;
        }
        if state.get(start_item.key.as_str()).copied() != Some(Mark::Unvisited) {
            continue;
        }

        let mut path: Vec<&str> = Vec::new();
        let mut cursor: Option<&str> = Some(start_item.key.as_str());

        loop {
            let Some(key) = cursor else {
                for k in &path {
                    state.insert(*k, Mark::Done);
                }
                break;
            };
            match state.get(key).copied() {
                Some(Mark::Done) | None => {
                    for k in &path {
                        state.insert(*k, Mark::Done);
                    }
                    break;
                }
                Some(Mark::Visiting) => {
                    let cycle: Vec<&str> = path
                        .iter()
                        .copied()
                        .skip_while(|k| *k != key)
                        .chain(std::iter::once(key))
                        .collect();
                    let signature = cycle.iter().copied().collect::<Vec<_>>().join("->");
                    if reported.insert(signature.clone()) {
                        findings.push(Finding {
                            severity: "error",
                            code: "parent_cycle",
                            item_key: Some(key.to_string()),
                            message: format!("parent_key cycle detected: {}", signature),
                        });
                    }
                    for k in &path {
                        state.insert(*k, Mark::Done);
                    }
                    break;
                }
                Some(Mark::Unvisited) => {
                    state.insert(key, Mark::Visiting);
                    path.push(key);
                    let next_parent = by_key
                        .get(key)
                        .and_then(|item| item.parent_key.as_deref())
                        .filter(|p| !p.is_empty() && *p != key);
                    cursor = next_parent;
                }
            }
        }
    }
}

fn finding_to_dict<'py>(py: Python<'py>, finding: &Finding) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new_bound(py);
    dict.set_item("severity", finding.severity)?;
    dict.set_item("code", finding.code)?;
    dict.set_item("item_key", finding.item_key.clone())?;
    dict.set_item("message", &finding.message)?;
    Ok(dict)
}

fn build_report<'py>(
    py: Python<'py>,
    sprint: &SprintInput,
    findings: Vec<Finding>,
) -> PyResult<Bound<'py, PyDict>> {
    let errors: Vec<&Finding> = findings.iter().filter(|f| f.severity == "error").collect();
    let warnings: Vec<&Finding> = findings.iter().filter(|f| f.severity == "warning").collect();
    let infos: Vec<&Finding> = findings.iter().filter(|f| f.severity == "info").collect();

    let report = PyDict::new_bound(py);
    report.set_item("sprint_id", &sprint.id)?;
    report.set_item("sprint_name", &sprint.name)?;
    report.set_item("item_count", sprint.items.len())?;
    report.set_item("ok", errors.is_empty())?;
    report.set_item("error_count", errors.len())?;
    report.set_item("warning_count", warnings.len())?;
    report.set_item("info_count", infos.len())?;

    let findings_list = PyList::empty_bound(py);
    for finding in &findings {
        findings_list.append(finding_to_dict(py, finding)?)?;
    }
    report.set_item("findings", findings_list)?;
    Ok(report)
}

/// Validate a sprint plan supplied as JSON bytes.
///
/// Returns a dict::
///
///     {
///       "sprint_id": str,
///       "sprint_name": str,
///       "item_count": int,
///       "ok": bool,
///       "error_count": int,
///       "warning_count": int,
///       "info_count": int,
///       "findings": [
///         {"severity": "error"|"warning"|"info", "code": str,
///          "item_key": str|None, "message": str},
///         ...
///       ],
///     }
#[pyfunction]
fn validate_sprint_plan_bytes<'py>(
    py: Python<'py>,
    payload: &Bound<'py, PyBytes>,
) -> PyResult<Bound<'py, PyDict>> {
    let bytes = payload.as_bytes();
    let sprint: SprintInput = serde_json::from_slice(bytes)
        .map_err(|e| PyValueError::new_err(format!("invalid sprint JSON: {}", e)))?;

    let findings = py.allow_threads(|| validate(&sprint));
    build_report(py, &sprint, findings)
}

/// Validate a sprint plan supplied as a JSON string.
#[pyfunction]
fn validate_sprint_plan_str<'py>(py: Python<'py>, payload: &str) -> PyResult<Bound<'py, PyDict>> {
    let sprint: SprintInput = serde_json::from_str(payload)
        .map_err(|e| PyValueError::new_err(format!("invalid sprint JSON: {}", e)))?;
    let findings = py.allow_threads(|| validate(&sprint));
    build_report(py, &sprint, findings)
}

/// Return the crate version string.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn sendsprint_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_sprint_plan_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(validate_sprint_plan_str, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}
