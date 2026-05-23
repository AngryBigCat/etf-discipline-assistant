from __future__ import annotations

import pandas as pd

from src.ui.labels import rename_columns


def test_rename_columns_symbol():
    df = pd.DataFrame({"symbol": ["A500"], "name": ["中证A500"]})
    result = rename_columns(df)
    assert "标的代码" in result.columns
    assert "symbol" not in result.columns
    assert result["标的代码"].iloc[0] == "A500"
