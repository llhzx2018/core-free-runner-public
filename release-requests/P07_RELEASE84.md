# P07 · VF Server Ops 0.1.0-release84

Formal release of the verified public distribution build 0.1.0-release84.

- Source main: llhzx2018/vf-server-ops @ 46f309a583a23a330542220caf38ff167f46ad8c
- Distribution source PR: llhzx2018/core-free-runner-public#2179
- Distribution merged main: f8f923093a7e3a1c56c2b3c2a7a2e5a0ed91d49f
- Public runtime build: 0.1.0-release84
- System Care: 0.1.0-rc42
- Network Node: 0.1.0-rc12
- VPS Audit: V2.2.4

## Changes

- Automatic backup status shows a concise conclusion, remote health, and context-aware next action instead of a raw per-site engineering dump.
- Initial Google+B2 backup verification remains one-site first, then exact current-site-set verification before scheduling is allowed.
- Ordinary module failure pages show a Chinese task name and recovery guidance, not raw exit codes or paths.
- Main menu routes 1–5, safe confirmations, resource guardrails, migration protection, and no automatic DNS/source deletion remain unchanged.

## Evidence and boundaries

P07 Distribution Gate, Stable Installer Smoke, Toolbox Smoke, Beginner Menu Gate, System Care Smoke, Runner Trigger Scope, and Workflow Archive Integrity all passed on Public Distribution candidate 559258c0af7cc516e18004a721b668daf1420dda.

Production operations / real migration / restore / DNS changes were NOT RUN. Owner production acceptance is separate and cannot be inferred from synthetic machine checks.

Stable public installer: https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-toolbox.sh
