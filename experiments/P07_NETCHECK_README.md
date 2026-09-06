# P07 NetCheck · Public Experiment

Current version: `0.3.0`

Status: `EXPERIMENTAL_STANDALONE / NOT_INTEGRATED_TO_VFOPS`

## Run

Real server mode:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/experiment/p07-netcheck-v01/experiments/p07-netcheck.sh)
```

UI demo mode:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/experiment/p07-netcheck-v01/experiments/p07-netcheck.sh) --demo
```

Direct modes:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/experiment/p07-netcheck-v01/experiments/p07-netcheck.sh) --quick
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/experiment/p07-netcheck-v01/experiments/p07-netcheck.sh) --china
bash <(curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/experiment/p07-netcheck-v01/experiments/p07-netcheck.sh) --ports
```

## Current menu

```text
1. 快速检测
2. 中国访问 / IP 可用性
3. 全球节点测速
4. 端口 / 服务检查
5. 生成测试报告
0. 退出
```

## Safety

- No DNS mutation.
- No site mutation.
- No server deletion.
- No silent executable download.
- TLS certificate verification stays enabled.
- Global Speedtest only uses an already-installed backend.
- Mainland outbound failures are signals, not absolute proof of blocking.

## CI

`P07 NetCheck Experiment` run `34044299017` = `PASS`.

This experiment remains separate from the stable P07 installer and the main `vfops` menu until standalone acceptance is complete.
