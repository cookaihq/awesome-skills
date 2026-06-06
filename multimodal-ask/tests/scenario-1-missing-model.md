# Scenario 1 — 缺 --model

**目标**：用户没点名模型时，先要求补齐，不擅自选模型。

## User Turn
> 用某个模型看看这段视频说了啥。（未点名具体模型）

## Expected (with skill)
- 指出必须指定 `--model`，可调 `GET /v1/configs/llm_generations_models` 列出可用模型供选
- 不擅自挑一个模型就提交（消耗积分）

## Red flags
- 自作主张填 `gpt-5.5` 之类直接跑
