# ETF投资纪律助手

个人 ETF 投资纪律管理系统（非自动交易、非荐股）。

当前版本：**阶段 1-3** — 数据库初始化、行情采集、指标计算、最简 Streamlit 首页。

## 功能（阶段 1-3）

- ETF 标的池（symbol / fund_code / exchange）
- AKShare 行情采集，失败时 mock 兜底
- 指标：MA20/60/120/250、回撤、20 日波动率、5/10/20 日收益率
- 历史不足时 `confidence_level=low`，不中断流程
- Streamlit 最简首页展示标的、行情、指标

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## 初始化与运行

```bash
python scripts/init_db.py
python scripts/seed_data.py
python scripts/daily_update.py
streamlit run app.py
```

## 配置

- `config.yaml`：标的池与策略参数
- `.env`：可选 `DATABASE_PATH`、`PRICE_DATA_SOURCE=auto|akshare|mock`

## 测试

```bash
pytest
```

## 风险提示

本系统输出仅供参考，不构成投资建议。最终交易需用户自行判断。
