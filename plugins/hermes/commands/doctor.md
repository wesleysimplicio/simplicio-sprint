---
name: doctor
description: Check whether the machine + credentials are ready for autonomous delivery.
exec: sendsprint doctor
---

Run `sendsprint doctor`. Report a single line: `<green> green / <yellow> yellow / <red> red`. List the first blocker if any red row is present. Block `/sprint` while a blocker exists.
