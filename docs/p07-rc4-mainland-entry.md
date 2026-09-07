# P07 RC4 mainland toolbox promotion

- Toolbox version: `0.1.0-preview6`
- Slot 2 module: `P07 VPS 一键验机 2.0 / 2.0.0-rc4-zh`
- Exact RC4 source commit: `1197372f0b32b7cc9a8b35736c30563cb36633c9`
- SHA256: `54325e92bdf78a90c74b5fed73be9d0633b402659fdfa2848dc751ff23efaecd`
- Mainland real probe run: `34083627031` PASS
- RC4 semantic gate: `34083787219` PASS
- Mainland regions: 北京（清华 TUNA/北外候选池）、上海（上交 SJTUG）、华南深圳（南科大 SUSTech）、西南重庆（重庆邮电 CQUPT）
- Measurement: bounded HTTPS mirror download + first-byte time.
- Boundary: mainland node → VPS reference only; not a mainland-origin inbound reachability verdict.
- User-facing entry remains only `installers/p07-toolbox.sh`.
