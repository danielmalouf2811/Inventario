from __future__ import annotations

import hashlib
import secrets
import sqlite3
from io import BytesIO
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path("data")
PRODUCTS_FILE = DATA_DIR / "products.csv"
SALES_FILE = DATA_DIR / "sales.csv"
COSTS_FILE = DATA_DIR / "monthly_costs.csv"
CATEGORIES_FILE = DATA_DIR / "categories.csv"
AUTH_DB = DATA_DIR / "users.db"

PRODUCT_COLUMNS = ["id", "name", "category", "stock", "cost_price", "sale_price", "updated_at"]
SALES_COLUMNS = [
    "id",
    "sale_date",
    "product_id",
    "product_name",
    "product_category",
    "quantity",
    "unit_cost",
    "unit_sale_price",
    "subtotal",
    "pays_tax",
    "iva",
    "total_with_tax",
    "cost",
    "profit_before_isr",
    "isr",
    "net_profit",
]
COSTS_COLUMNS = ["year_month", "fixed_cost", "variable_cost", "notes", "updated_at"]
CATEGORY_COLUMNS = ["name", "created_at"]


def _safe_read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    """Read a CSV safely and recreate it if missing, empty, or malformed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        df = pd.DataFrame(columns=columns)
        df.to_csv(path, index=False)
        return df
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        df = pd.DataFrame(columns=columns)
        df.to_csv(path, index=False)
        return df
    except Exception:
        df = pd.DataFrame(columns=columns)
        df.to_csv(path, index=False)
        return df

    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df[columns]



# ---------- Auth ----------
def get_auth_conn() -> sqlite3.Connection:
    AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(AUTH_DB)


def init_auth_db() -> None:
    with get_auth_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def hash_password(password: str, salt: str) -> str:
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        120000,
    )
    return hashed.hex()


def create_user(username: str, password: str) -> tuple[bool, str]:
    if not username.strip() or not password:
        return False, "Usuario y contraseña son obligatorios."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    clean_username = username.strip().lower()
    salt = secrets.token_hex(16)
    pwd_hash = hash_password(password, salt)

    try:
        with get_auth_conn() as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (clean_username, pwd_hash, salt, datetime.utcnow().isoformat()),
            )
        return True, "Cuenta creada correctamente."
    except sqlite3.IntegrityError:
        return False, "Ese usuario ya existe."


def authenticate_user(username: str, password: str) -> tuple[bool, str]:
    clean_username = username.strip().lower()
    if not clean_username or not password:
        return False, "Completa usuario y contraseña."

    with get_auth_conn() as conn:
        row = conn.execute(
            "SELECT username, password_hash, salt FROM users WHERE username = ?",
            (clean_username,),
        ).fetchone()

    if row is None:
        return False, "Usuario o contraseña incorrectos."

    expected_hash = row[1]
    salt = row[2]
    if hash_password(password, salt) != expected_hash:
        return False, "Usuario o contraseña incorrectos."

    return True, row[0]


def auth_screen() -> None:
    st.title("🔐 Acceso a la aplicación")
    st.caption("Inicia sesión o crea una cuenta para continuar.")

    tabs = st.tabs(["Iniciar sesión", "Registro"])

    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar")

            if submit_login:
                ok, result = authenticate_user(username, password)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.username = result
                    st.success("Inicio de sesión exitoso.")
                    st.rerun()
                else:
                    st.error(result)

    with tabs[1]:
        with st.form("register_form", clear_on_submit=True):
            new_username = st.text_input("Usuario nuevo")
            new_password = st.text_input("Contraseña", type="password")
            confirm_password = st.text_input("Confirmar contraseña", type="password")
            submit_register = st.form_submit_button("Crear cuenta")

            if submit_register:
                if new_password != confirm_password:
                    st.error("Las contraseñas no coinciden.")
                else:
                    ok, message = create_user(new_username, new_password)
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)


# ---------- Data ----------
def ensure_data_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not PRODUCTS_FILE.exists():
        pd.DataFrame(columns=PRODUCT_COLUMNS).to_csv(PRODUCTS_FILE, index=False)
    if not SALES_FILE.exists():
        pd.DataFrame(columns=SALES_COLUMNS).to_csv(SALES_FILE, index=False)
    if not COSTS_FILE.exists():
        pd.DataFrame(columns=COSTS_COLUMNS).to_csv(COSTS_FILE, index=False)
    if not CATEGORIES_FILE.exists():
        pd.DataFrame(columns=CATEGORY_COLUMNS).to_csv(CATEGORIES_FILE, index=False)


def load_products() -> pd.DataFrame:
    df = _safe_read_csv(PRODUCTS_FILE, PRODUCT_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=PRODUCT_COLUMNS)

    numeric_cols = ["id", "stock", "cost_price", "sale_price"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["id"] = df["id"].astype(int)
    df["stock"] = df["stock"].astype(int)
    return df[PRODUCT_COLUMNS]


def load_categories() -> pd.DataFrame:
    df = _safe_read_csv(CATEGORIES_FILE, CATEGORY_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=CATEGORY_COLUMNS)
    return df[CATEGORY_COLUMNS]


def save_categories(df: pd.DataFrame) -> None:
    df[CATEGORY_COLUMNS].to_csv(CATEGORIES_FILE, index=False)


def add_category(name: str) -> tuple[bool, str]:
    clean_name = name.strip()
    if not clean_name:
        return False, "La categoría es obligatoria."

    categories = load_categories()
    exists = categories["name"].str.lower().eq(clean_name.lower()).any() if not categories.empty else False
    if exists:
        return False, "La categoría ya existe."

    row = {"name": clean_name, "created_at": datetime.utcnow().isoformat()}
    categories = pd.concat([categories, pd.DataFrame([row])], ignore_index=True)
    save_categories(categories)
    return True, "Categoría creada correctamente."


def sync_categories_from_products() -> None:
    products = load_products()
    categories = load_categories()
    existing = set(categories["name"].str.lower().tolist()) if not categories.empty else set()

    new_rows = []
    if not products.empty:
        for cat in products["category"].dropna().astype(str).str.strip():
            if cat and cat.lower() not in existing:
                new_rows.append({"name": cat, "created_at": datetime.utcnow().isoformat()})
                existing.add(cat.lower())

    if new_rows:
        categories = pd.concat([categories, pd.DataFrame(new_rows)], ignore_index=True)
        save_categories(categories)


def save_products(df: pd.DataFrame) -> None:
    df[PRODUCT_COLUMNS].to_csv(PRODUCTS_FILE, index=False)


def load_sales() -> pd.DataFrame:
    df = _safe_read_csv(SALES_FILE, SALES_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=SALES_COLUMNS)

    if "income" in df.columns and "subtotal" not in df.columns:
        df["subtotal"] = pd.to_numeric(df["income"], errors="coerce").fillna(0.0)
    if "profit" in df.columns and "profit_before_isr" not in df.columns:
        df["profit_before_isr"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0.0)

    defaults = {
        "product_category": "",
        "subtotal": 0.0,
        "pays_tax": False,
        "iva": 0.0,
        "total_with_tax": 0.0,
        "profit_before_isr": 0.0,
        "isr": 0.0,
        "net_profit": 0.0,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    numeric_cols = [
        "id",
        "product_id",
        "quantity",
        "unit_cost",
        "unit_sale_price",
        "subtotal",
        "iva",
        "total_with_tax",
        "cost",
        "profit_before_isr",
        "isr",
        "net_profit",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["id"] = df["id"].astype(int)
    df["product_id"] = df["product_id"].astype(int)
    df["quantity"] = df["quantity"].astype(int)
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df["pays_tax"] = df["pays_tax"].astype(str).str.lower().isin(["true", "1", "si", "sí", "yes"])
    return df[SALES_COLUMNS]


def save_sales(df: pd.DataFrame) -> None:
    df_to_save = df.copy()
    if not df_to_save.empty:
        df_to_save["sale_date"] = pd.to_datetime(df_to_save["sale_date"]).dt.strftime("%Y-%m-%d")
    df_to_save[SALES_COLUMNS].to_csv(SALES_FILE, index=False)


def load_monthly_costs() -> pd.DataFrame:
    df = _safe_read_csv(COSTS_FILE, COSTS_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=COSTS_COLUMNS)

    df["fixed_cost"] = pd.to_numeric(df["fixed_cost"], errors="coerce").fillna(0.0)
    df["variable_cost"] = pd.to_numeric(df["variable_cost"], errors="coerce").fillna(0.0)
    return df[COSTS_COLUMNS]


def save_monthly_costs(df: pd.DataFrame) -> None:
    df[COSTS_COLUMNS].to_csv(COSTS_FILE, index=False)


def next_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1
    return int(df["id"].max()) + 1


def add_product(name: str, category: str, stock: int, cost_price: float, sale_price: float) -> None:
    products = load_products()
    new_row = {
        "id": next_id(products),
        "name": name,
        "category": category,
        "stock": int(stock),
        "cost_price": float(cost_price),
        "sale_price": float(sale_price),
        "updated_at": datetime.utcnow().isoformat(),
    }
    products = pd.concat([products, pd.DataFrame([new_row])], ignore_index=True)
    save_products(products)


def get_product_by_name(name: str) -> pd.Series | None:
    products = load_products()
    match = products[products["name"].str.lower() == name.lower()]
    if match.empty:
        return None
    return match.iloc[0]


def product_exists(name: str) -> bool:
    return get_product_by_name(name) is not None


def product_exists_in_category(name: str, category: str, exclude_id: int | None = None) -> bool:
    products = load_products()
    if products.empty:
        return False
    mask = (
        products["name"].astype(str).str.lower().eq(name.strip().lower())
        & products["category"].astype(str).str.lower().eq(category.strip().lower())
    )
    if exclude_id is not None:
        mask = mask & (products["id"] != exclude_id)
    return products[mask].shape[0] > 0


def get_unique_categories(include_all: bool = False) -> list[str]:
    categories = load_categories()
    items = sorted(categories["name"].dropna().astype(str).unique().tolist()) if not categories.empty else []
    if include_all:
        return ["Todas las categorías"] + items
    return items


def get_products_by_category(category: str | None = None) -> pd.DataFrame:
    products = load_products()
    if products.empty:
        return products
    if not category or category == "Todas las categorías":
        return products
    return products[products["category"] == category].copy()


def filter_sales_by_category_product(sales_df: pd.DataFrame, category: str, product: str) -> pd.DataFrame:
    filtered = sales_df.copy()
    if category != "Todas las categorías":
        filtered = filtered[filtered["product_category"] == category]
    if product != "Todos los productos":
        filtered = filtered[filtered["product_name"] == product]
    return filtered


def update_product(product_id: int, name: str, category: str, stock: int, cost_price: float, sale_price: float) -> None:
    products = load_products()
    idx = products.index[products["id"] == product_id]
    if len(idx) == 0:
        return

    products.loc[idx, ["name", "category", "stock", "cost_price", "sale_price", "updated_at"]] = [
        name,
        category,
        int(stock),
        float(cost_price),
        float(sale_price),
        datetime.utcnow().isoformat(),
    ]
    save_products(products)


def delete_product(product_id: int) -> None:
    products = load_products()
    products = products[products["id"] != product_id].copy()
    save_products(products)


def register_sale(product_id: int, quantity: int, sale_dt: date, pays_tax: bool) -> tuple[bool, str]:
    products = load_products()
    sales = load_sales()

    match = products[products["id"] == product_id]
    if match.empty:
        return False, "Producto no encontrado."

    product = match.iloc[0]
    current_stock = int(product["stock"])
    quantity = int(quantity)

    if quantity <= 0:
        return False, "La cantidad debe ser mayor a 0."
    if quantity > current_stock:
        return False, "Stock insuficiente para registrar la venta."

    unit_cost = float(product["cost_price"])
    unit_price = float(product["sale_price"])
    subtotal = unit_price * quantity
    iva = subtotal * 0.12 if pays_tax else 0.0
    total_with_tax = subtotal + iva
    cost = unit_cost * quantity
    profit_before_isr = subtotal - cost
    isr = max(profit_before_isr, 0) * 0.25
    net_profit = profit_before_isr - isr

    sale_row = {
        "id": next_id(sales),
        "sale_date": sale_dt.isoformat(),
        "product_id": int(product["id"]),
        "product_name": product["name"],
        "product_category": product["category"],
        "quantity": quantity,
        "unit_cost": unit_cost,
        "unit_sale_price": unit_price,
        "subtotal": subtotal,
        "pays_tax": bool(pays_tax),
        "iva": iva,
        "total_with_tax": total_with_tax,
        "cost": cost,
        "profit_before_isr": profit_before_isr,
        "isr": isr,
        "net_profit": net_profit,
    }

    sales = pd.concat([sales, pd.DataFrame([sale_row])], ignore_index=True)
    save_sales(sales)

    products.loc[products["id"] == product_id, "stock"] = current_stock - quantity
    products.loc[products["id"] == product_id, "updated_at"] = datetime.utcnow().isoformat()
    save_products(products)

    return True, "Venta registrada (con impuestos si aplica) y stock actualizado."


def upsert_monthly_cost(year_month: str, fixed_cost: float, variable_cost: float, notes: str) -> None:
    costs = load_monthly_costs()
    now = datetime.utcnow().isoformat()
    existing = costs["year_month"] == year_month

    if existing.any():
        costs.loc[existing, ["fixed_cost", "variable_cost", "notes", "updated_at"]] = [
            float(fixed_cost),
            float(variable_cost),
            notes,
            now,
        ]
    else:
        row = {
            "year_month": year_month,
            "fixed_cost": float(fixed_cost),
            "variable_cost": float(variable_cost),
            "notes": notes,
            "updated_at": now,
        }
        costs = pd.concat([costs, pd.DataFrame([row])], ignore_index=True)

    save_monthly_costs(costs)


def build_daily_summary(sales_df: pd.DataFrame) -> pd.DataFrame:
    if sales_df.empty:
        return pd.DataFrame(columns=["period", "ventas_brutas", "iva", "ingresos_netos_sin_iva", "costo_ventas", "utilidad_antes_isr", "isr", "utilidad_neta"])

    temp = sales_df.copy()
    temp["period"] = pd.to_datetime(temp["sale_date"]).dt.date
    out = (
        temp.groupby("period", as_index=False)
        .agg(
            ventas_brutas=("subtotal", "sum"),
            iva=("iva", "sum"),
            ingresos_netos_sin_iva=("subtotal", "sum"),
            costo_ventas=("cost", "sum"),
            utilidad_antes_isr=("profit_before_isr", "sum"),
            isr=("isr", "sum"),
            utilidad_neta=("net_profit", "sum"),
        )
        .sort_values("period")
    )
    return out


def build_monthly_summary(sales_df: pd.DataFrame, costs_df: pd.DataFrame) -> pd.DataFrame:
    monthly_sales = pd.DataFrame(
        columns=[
            "year_month",
            "ventas_brutas",
            "iva",
            "ingresos_netos_sin_iva",
            "costo_ventas",
            "utilidad_bruta",
            "ventas_con_iva",
            "ventas_sin_iva",
        ]
    )

    if not sales_df.empty:
        temp = sales_df.copy()
        temp["year_month"] = pd.to_datetime(temp["sale_date"]).dt.to_period("M").astype(str)
        monthly_sales = (
            temp.groupby("year_month", as_index=False)
            .agg(
                ventas_brutas=("subtotal", "sum"),
                iva=("iva", "sum"),
                ingresos_netos_sin_iva=("subtotal", "sum"),
                costo_ventas=("cost", "sum"),
                utilidad_bruta=("profit_before_isr", "sum"),
                ventas_con_iva=("pays_tax", "sum"),
                ventas_sin_iva=("pays_tax", lambda x: (~x).sum()),
            )
            .sort_values("year_month")
        )

    if monthly_sales.empty and costs_df.empty:
        return pd.DataFrame(
            columns=[
                "year_month",
                "ventas_brutas",
                "ventas_con_iva",
                "ventas_sin_iva",
                "iva",
                "ingresos_netos_sin_iva",
                "costo_ventas",
                "utilidad_bruta",
                "costos_fijos",
                "costos_variables",
                "utilidad_operativa",
                "utilidad_antes_isr",
                "isr",
                "utilidad_neta",
            ]
        )

    merged = monthly_sales.merge(costs_df, on="year_month", how="outer")
    for col in ["ventas_brutas", "iva", "ingresos_netos_sin_iva", "costo_ventas", "utilidad_bruta", "ventas_con_iva", "ventas_sin_iva"]:
        merged[col] = pd.to_numeric(merged.get(col, 0), errors="coerce").fillna(0)
    merged["fixed_cost"] = pd.to_numeric(merged.get("fixed_cost", 0), errors="coerce").fillna(0)
    merged["variable_cost"] = pd.to_numeric(merged.get("variable_cost", 0), errors="coerce").fillna(0)

    merged["costos_fijos"] = merged["fixed_cost"]
    merged["costos_variables"] = merged["variable_cost"]
    merged["utilidad_operativa"] = merged["utilidad_bruta"] - merged["costos_fijos"] - merged["costos_variables"]
    merged["utilidad_antes_isr"] = merged["utilidad_operativa"]
    merged["isr"] = merged["utilidad_antes_isr"].apply(lambda x: x * 0.25 if x > 0 else 0)
    merged["utilidad_neta"] = merged["utilidad_antes_isr"] - merged["isr"]

    return merged[
        [
            "year_month",
            "ventas_brutas",
            "ventas_con_iva",
            "ventas_sin_iva",
            "iva",
            "ingresos_netos_sin_iva",
            "costo_ventas",
            "utilidad_bruta",
            "costos_fijos",
            "costos_variables",
            "utilidad_operativa",
            "utilidad_antes_isr",
            "isr",
            "utilidad_neta",
        ]
    ].sort_values("year_month")


def build_inventory_export(products_df: pd.DataFrame) -> pd.DataFrame:
    if products_df.empty:
        return pd.DataFrame(
            columns=[
                "Fecha",
                "Producto",
                "Categoría",
                "Stock",
                "Costo_unitario",
                "Precio_venta",
                "Valor_inventario",
            ]
        )

    out = products_df.copy()
    out["Fecha"] = pd.to_datetime(out["updated_at"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Fecha"] = out["Fecha"].fillna(date.today().isoformat())
    out["Producto"] = out["name"]
    out["Categoría"] = out["category"]
    out["Stock"] = pd.to_numeric(out["stock"], errors="coerce").fillna(0).astype(int)
    out["Costo_unitario"] = pd.to_numeric(out["cost_price"], errors="coerce").fillna(0.0)
    out["Precio_venta"] = pd.to_numeric(out["sale_price"], errors="coerce").fillna(0.0)
    out["Valor_inventario"] = out["Stock"] * out["Costo_unitario"]
    return out[
        ["Fecha", "Producto", "Categoría", "Stock", "Costo_unitario", "Precio_venta", "Valor_inventario"]
    ].sort_values(["Fecha", "Producto"])


def build_cashflow_export(sales_df: pd.DataFrame, costs_df: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    if not sales_df.empty:
        sales = sales_df.copy()
        sales["Fecha"] = pd.to_datetime(sales["sale_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        sales["Tipo"] = "Ingreso"
        sales["Categoría"] = "Ventas"
        sales["Descripción"] = sales["product_name"]
        sales["Cantidad"] = pd.to_numeric(sales["quantity"], errors="coerce").fillna(0).astype(int)
        sales["Precio_unitario"] = pd.to_numeric(sales["unit_sale_price"], errors="coerce").fillna(0.0)
        sales["paga_impuestos"] = sales["pays_tax"].map({True: "Sí", False: "No"})
        sales["iva"] = pd.to_numeric(sales["iva"], errors="coerce").fillna(0.0)
        sales["subtotal"] = pd.to_numeric(sales["subtotal"], errors="coerce").fillna(0.0)
        sales["total_con_iva"] = pd.to_numeric(sales["total_with_tax"], errors="coerce").fillna(0.0)
        sales["utilidad_antes_isr"] = pd.to_numeric(sales["profit_before_isr"], errors="coerce").fillna(0.0)
        sales["isr"] = pd.to_numeric(sales["isr"], errors="coerce").fillna(0.0)
        sales["utilidad_neta"] = pd.to_numeric(sales["net_profit"], errors="coerce").fillna(0.0)
        sales["Total"] = sales["subtotal"]
        sales["Mes"] = pd.to_datetime(sales["sale_date"], errors="coerce").dt.month.fillna(0).astype(int)
        sales["Año"] = pd.to_datetime(sales["sale_date"], errors="coerce").dt.year.fillna(0).astype(int)
        frames.append(
            sales[
                [
                    "Fecha",
                    "Tipo",
                    "Categoría",
                    "Descripción",
                    "Cantidad",
                    "Precio_unitario",
                    "Total",
                    "Mes",
                    "Año",
                    "paga_impuestos",
                    "iva",
                    "subtotal",
                    "total_con_iva",
                    "utilidad_antes_isr",
                    "isr",
                    "utilidad_neta",
                ]
            ]
        )

    if not costs_df.empty:
        costs = costs_df.copy()
        period_date = pd.to_datetime(costs["year_month"] + "-01", errors="coerce")

        fixed = pd.DataFrame(
            {
                "Fecha": period_date.dt.strftime("%Y-%m-%d"),
                "Tipo": "Egreso",
                "Categoría": "Costos fijos",
                "Descripción": costs["notes"].fillna("").replace("", "Costo fijo mensual"),
                "Cantidad": 1,
                "Precio_unitario": pd.to_numeric(costs["fixed_cost"], errors="coerce").fillna(0.0),
                "Total": pd.to_numeric(costs["fixed_cost"], errors="coerce").fillna(0.0),
                "Mes": period_date.dt.month.fillna(0).astype(int),
                "Año": period_date.dt.year.fillna(0).astype(int),
                "paga_impuestos": "No",
                "iva": 0.0,
                "subtotal": pd.to_numeric(costs["fixed_cost"], errors="coerce").fillna(0.0),
                "total_con_iva": pd.to_numeric(costs["fixed_cost"], errors="coerce").fillna(0.0),
                "utilidad_antes_isr": 0.0,
                "isr": 0.0,
                "utilidad_neta": 0.0,
            }
        )
        variable = pd.DataFrame(
            {
                "Fecha": period_date.dt.strftime("%Y-%m-%d"),
                "Tipo": "Egreso",
                "Categoría": "Costos variables",
                "Descripción": costs["notes"].fillna("").replace("", "Costo variable mensual"),
                "Cantidad": 1,
                "Precio_unitario": pd.to_numeric(costs["variable_cost"], errors="coerce").fillna(0.0),
                "Total": pd.to_numeric(costs["variable_cost"], errors="coerce").fillna(0.0),
                "Mes": period_date.dt.month.fillna(0).astype(int),
                "Año": period_date.dt.year.fillna(0).astype(int),
                "paga_impuestos": "No",
                "iva": 0.0,
                "subtotal": pd.to_numeric(costs["variable_cost"], errors="coerce").fillna(0.0),
                "total_con_iva": pd.to_numeric(costs["variable_cost"], errors="coerce").fillna(0.0),
                "utilidad_antes_isr": 0.0,
                "isr": 0.0,
                "utilidad_neta": 0.0,
            }
        )
        frames.extend([fixed, variable])

    if not frames:
        return pd.DataFrame(
            columns=["Fecha", "Tipo", "Categoría", "Descripción", "Cantidad", "Precio_unitario", "Total", "Mes", "Año", "paga_impuestos", "iva", "subtotal", "total_con_iva", "utilidad_antes_isr", "isr", "utilidad_neta"]
        )

    out = pd.concat(frames, ignore_index=True)
    out["Fecha"] = out["Fecha"].fillna(date.today().isoformat())
    out["Cantidad"] = pd.to_numeric(out["Cantidad"], errors="coerce").fillna(0).astype(int)
    out["Precio_unitario"] = pd.to_numeric(out["Precio_unitario"], errors="coerce").fillna(0.0)
    out["Total"] = pd.to_numeric(out["Total"], errors="coerce").fillna(0.0)
    out["Mes"] = pd.to_numeric(out["Mes"], errors="coerce").fillna(0).astype(int)
    out["Año"] = pd.to_numeric(out["Año"], errors="coerce").fillna(0).astype(int)
    return out.sort_values(["Fecha", "Tipo", "Categoría"]).reset_index(drop=True)


def build_summary_export(cashflow_df: pd.DataFrame) -> pd.DataFrame:
    if cashflow_df.empty:
        return pd.DataFrame(columns=["Año", "Mes", "Ingresos", "Egresos", "Utilidad"])

    temp = cashflow_df.copy()
    temp["Ingresos"] = temp.apply(lambda row: row["Total"] if row["Tipo"] == "Ingreso" else 0.0, axis=1)
    temp["Egresos"] = temp.apply(lambda row: row["Total"] if row["Tipo"] == "Egreso" else 0.0, axis=1)
    grouped = (
        temp.groupby(["Año", "Mes"], as_index=False)
        .agg(Ingresos=("Ingresos", "sum"), Egresos=("Egresos", "sum"))
        .sort_values(["Año", "Mes"])
    )
    grouped["Utilidad"] = grouped["Ingresos"] - grouped["Egresos"]
    return grouped


def generate_excel_file(products_df: pd.DataFrame, sales_df: pd.DataFrame, costs_df: pd.DataFrame) -> bytes:
    inventario = build_inventory_export(products_df)
    flujo_caja = build_cashflow_export(sales_df, costs_df)
    resumen = build_summary_export(flujo_caja)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        inventario.to_excel(writer, sheet_name="Inventario", index=False)
        flujo_caja.to_excel(writer, sheet_name="Flujo_Caja", index=False)
        resumen.to_excel(writer, sheet_name="Resumen", index=False)
    output.seek(0)
    return output.getvalue()


def inventory_tab() -> None:
    st.subheader("Inventario de productos")

    if "show_new_category_form" not in st.session_state:
        st.session_state.show_new_category_form = False
    if "show_new_product_form" not in st.session_state:
        st.session_state.show_new_product_form = False

    b1, b2 = st.columns(2)
    if b1.button("Agregar nueva categoría"):
        st.session_state.show_new_category_form = not st.session_state.show_new_category_form
    if b2.button("Agregar nuevo producto"):
        st.session_state.show_new_product_form = not st.session_state.show_new_product_form

    if st.session_state.show_new_category_form:
        with st.form("create_category_form", clear_on_submit=True):
            new_category_name = st.text_input("Nombre de la categoría")
            create_category = st.form_submit_button("Guardar categoría")
            if create_category:
                ok, msg = add_category(new_category_name)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    if st.session_state.show_new_product_form:
        with st.form("create_product_form", clear_on_submit=True):
            categories = get_unique_categories()
            if not categories:
                st.info("Primero debes crear al menos una categoría.")
            product_name = st.text_input("Nombre del producto")
            category = st.selectbox("Categoría del producto", options=categories if categories else [""])
            stock = st.number_input("Stock inicial", min_value=0, step=1)
            c1, c2 = st.columns(2)
            cost_price = c1.number_input("Costo (precio de compra)", min_value=0.0, step=0.01)
            sale_price = c2.number_input("Precio de venta", min_value=0.0, step=0.01)
            create_product = st.form_submit_button("Guardar producto")
            if create_product:
                clean_product = product_name.strip()
                if not clean_product:
                    st.error("El nombre del producto es obligatorio.")
                elif not category:
                    st.error("Debes seleccionar una categoría.")
                elif product_exists_in_category(clean_product, category):
                    st.error("Ya existe un producto con ese nombre en la categoría seleccionada.")
                else:
                    add_product(clean_product, category, int(stock), float(cost_price), float(sale_price))
                    st.success("Producto agregado correctamente.")
                    st.rerun()

    products = load_products()
    categories = get_unique_categories(include_all=True)
    selected_category_filter = st.selectbox("Filtrar inventario por categoría", options=categories, key="inventory_category_filter")
    filtered_products = get_products_by_category(selected_category_filter)

    st.markdown("### Productos actuales")
    st.dataframe(filtered_products, use_container_width=True)

    if filtered_products.empty:
        st.info("No hay productos para la categoría seleccionada.")
        return

    product_names = filtered_products["name"].tolist()
    selected_product_name = st.selectbox("Producto", options=product_names, key="inventory_product_filter")
    selected = filtered_products[filtered_products["name"] == selected_product_name].iloc[0]
    selected_id = int(selected["id"])

    with st.form("edit_product_form"):
        e1, e2, e3 = st.columns(3)
        edit_name = e1.text_input("Nombre", value=str(selected["name"]))
        category_options = get_unique_categories()
        category_index = category_options.index(str(selected["category"])) if str(selected["category"]) in category_options else 0
        edit_category = e2.selectbox("Categoría", options=category_options, index=category_index)
        edit_stock = e3.number_input("Stock", min_value=0, step=1, value=int(selected["stock"]))

        e4, e5 = st.columns(2)
        edit_cost = e4.number_input("Costo", min_value=0.0, step=0.01, value=float(selected["cost_price"]))
        edit_price = e5.number_input("Precio de venta", min_value=0.0, step=0.01, value=float(selected["sale_price"]))

        updated = st.form_submit_button("Guardar cambios")
        if updated:
            clean_name = edit_name.strip()
            if not clean_name:
                st.error("El nombre del producto es obligatorio.")
            elif product_exists_in_category(clean_name, edit_category, exclude_id=selected_id):
                st.error("Ya existe un producto con ese nombre en la categoría seleccionada.")
            else:
                update_product(int(selected_id), clean_name, edit_category.strip(), int(edit_stock), float(edit_cost), float(edit_price))
                st.success("Producto actualizado.")
                st.rerun()

    st.markdown("### Eliminar producto")
    if st.button("Eliminar producto seleccionado", type="secondary"):
        delete_product(int(selected_id))
        st.success("Producto eliminado.")
        st.rerun()


def sales_tab() -> None:
    st.subheader("Registro de ventas")
    products = load_products()

    if products.empty:
        st.info("Agrega productos primero para poder registrar ventas.")
        return

    with st.form("sales_form", clear_on_submit=True):
        s1, s2, s3 = st.columns(3)
        product_id = s1.selectbox(
            "Producto",
            options=products["id"].tolist(),
            format_func=lambda pid: f"{products.loc[products['id'] == pid, 'name'].iloc[0]} (Stock: {int(products.loc[products['id'] == pid, 'stock'].iloc[0])})",
        )
        selected_category = products.loc[products["id"] == product_id, "category"].iloc[0]
        _ = s2.selectbox("Categoría", options=[selected_category], index=0)
        quantity = s3.number_input("Cantidad vendida", min_value=1, step=1)
        sale_dt = st.date_input("Fecha de venta", value=date.today())
        tax_choice = st.radio("¿Esta venta paga impuestos?", options=["Sí", "No"], horizontal=True)

        submit_sale = st.form_submit_button("Registrar venta")
        if submit_sale:
            pays_tax = tax_choice == "Sí"
            success, message = register_sale(int(product_id), int(quantity), sale_dt, pays_tax)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    sales_df = load_sales()
    st.markdown("### Historial de ventas")
    st.dataframe(sales_df, use_container_width=True)


def costs_tab() -> None:
    st.subheader("Costos mensuales")
    default_period = date.today().strftime("%Y-%m")

    with st.form("costs_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        period = c1.text_input("Periodo (YYYY-MM)", value=default_period)
        fixed_cost = c2.number_input("Costos fijos mensuales", min_value=0.0, step=0.01)
        variable_cost = c3.number_input("Costos variables mensuales", min_value=0.0, step=0.01)
        notes = st.text_area("Notas")

        submitted = st.form_submit_button("Guardar costos")
        if submitted:
            try:
                datetime.strptime(period, "%Y-%m")
                upsert_monthly_cost(period, float(fixed_cost), float(variable_cost), notes.strip())
                st.success("Costos guardados correctamente.")
                st.rerun()
            except ValueError:
                st.error("Formato de periodo inválido. Usa YYYY-MM.")

    costs_df = load_monthly_costs().sort_values("year_month")
    st.markdown("### Tabla de costos")
    st.dataframe(costs_df, use_container_width=True)


def dashboard_tab() -> None:
    st.subheader("Flujo de caja")
    sales_df = load_sales()
    costs_df = load_monthly_costs()
    products_df = load_products()

    categories = sorted(products_df["category"].dropna().astype(str).unique().tolist()) if not products_df.empty else []
    selected_category = st.selectbox("Filtrar por categoría", options=["Todas las categorías"] + categories, key="cashflow_category_filter")

    if selected_category == "Todas las categorías":
        product_options = sorted(products_df["name"].dropna().astype(str).unique().tolist()) if not products_df.empty else []
    else:
        product_options = (
            products_df[products_df["category"] == selected_category]["name"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        product_options = sorted(product_options)

    if selected_category != "Todas las categorías" and not product_options:
        st.info("No hay productos para la categoría seleccionada.")

    selected_product = st.selectbox("Filtrar por producto", options=["Todos los productos"] + product_options, key="cashflow_product_filter")
    filtered_sales = filter_sales_by_category_product(sales_df, selected_category, selected_product)

    daily_summary = build_daily_summary(filtered_sales)
    monthly_summary = build_monthly_summary(filtered_sales, costs_df)

    st.markdown("### Resumen diario (ventas)")
    st.dataframe(daily_summary, use_container_width=True)

    st.markdown("### Resumen mensual (ingresos vs costos vs utilidad)")
    st.dataframe(monthly_summary, use_container_width=True)

    if not monthly_summary.empty:
        total_gross_sales = monthly_summary["ventas_brutas"].sum()
        total_vat = monthly_summary["iva"].sum()
        total_net_income = monthly_summary["ingresos_netos_sin_iva"].sum()
        total_cost_sales = monthly_summary["costo_ventas"].sum()
        total_fixed = monthly_summary["costos_fijos"].sum()
        total_variable = monthly_summary["costos_variables"].sum()
        total_before_isr = monthly_summary["utilidad_antes_isr"].sum()
        total_isr = monthly_summary["isr"].sum()
        total_profit = monthly_summary["utilidad_neta"].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Ventas brutas", f"${total_gross_sales:,.2f}")
        m2.metric("IVA acumulado", f"${total_vat:,.2f}")
        m3.metric("Ingresos netos sin IVA", f"${total_net_income:,.2f}")

        n1, n2, n3 = st.columns(3)
        n1.metric("Costo de productos vendidos", f"${total_cost_sales:,.2f}")
        n2.metric("Costos fijos + variables", f"${(total_fixed + total_variable):,.2f}")
        n3.metric("Utilidad antes de ISR", f"${total_before_isr:,.2f}")

        p1, p2, p3 = st.columns(3)
        p1.metric("ISR (25%)", f"${total_isr:,.2f}")
        p2.metric("Utilidad neta final", f"${total_profit:,.2f}")
        p3.metric("Ventas con IVA / sin IVA", f"{int(monthly_summary['ventas_con_iva'].sum())} / {int(monthly_summary['ventas_sin_iva'].sum())}")

        chart_df = monthly_summary.melt(
            id_vars=["year_month"],
            value_vars=["ingresos_netos_sin_iva", "costo_ventas", "utilidad_neta"],
            var_name="concepto",
            value_name="monto",
        )
        fig = px.bar(
            chart_df,
            x="year_month",
            y="monto",
            color="concepto",
            barmode="group",
            title="Ingresos netos vs Costos de ventas vs Utilidad neta (mensual)",
            labels={"year_month": "Mes", "monto": "Monto"},
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no hay datos suficientes para mostrar el panel mensual.")

    st.markdown("### Exportación a Excel (Power BI)")
    try:
        excel_bytes = generate_excel_file(products_df, filtered_sales, costs_df)
        st.download_button(
            label="Descargar Excel",
            data=excel_bytes,
            file_name=f"inventario_flujo_caja_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Incluye hojas Inventario, Flujo_Caja y Resumen en formato tabular listo para Power BI.",
        )
    except ImportError:
        st.error("Falta la dependencia openpyxl para exportar a Excel. Agrégala a requirements.txt.")
    except Exception as exc:
        st.error(f"No se pudo generar el Excel: {exc}")


def app_screen() -> None:
    st.title("📦 Inventario y Flujo de Caja para pequeños negocios")
    st.caption("Interfaz simple para administrar productos, ventas y costos mensuales.")

    st.sidebar.success(f"Sesión activa: {st.session_state.username}")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    tabs = st.tabs(["Inventario", "Ventas", "Costos", "Panel"])
    with tabs[0]:
        inventory_tab()
    with tabs[1]:
        sales_tab()
    with tabs[2]:
        costs_tab()
    with tabs[3]:
        dashboard_tab()


def main() -> None:
    st.set_page_config(page_title="Inventario y Flujo de Caja", layout="wide")

    ensure_data_files()
    sync_categories_from_products()
    init_auth_db()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = ""

    if not st.session_state.logged_in:
        auth_screen()
        return

    app_screen()


if __name__ == "__main__":
    main()

