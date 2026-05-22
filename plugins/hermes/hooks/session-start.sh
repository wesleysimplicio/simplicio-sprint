#!/usr/bin/env bash
# SendSprint Hermes plugin — session-start banner.
cat <<'BANNER'
[SendSprint Hermes plugin loaded]

Commands:
  /sprint   /doctor   /watch   /full   /web

Chat triggers: "rode o sendsprint" · "run sendsprint" · "ejecutar sprint".
Runtime: external CLI (`sendsprint`). Credentials: OS keyring.
BANNER
