"""PostgreSQL 커넥션 풀 + 필터 유틸리티."""

import atexit

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from search.config import DATABASE_URL

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """싱글톤 커넥션 풀을 반환한다."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=2,
            max_size=5,
            configure=_configure_conn,
        )
        atexit.register(_pool.close)
    return _pool


def _configure_conn(conn):
    """새 커넥션마다 pgvector 타입을 등록한다."""
    register_vector(conn)


def get_connection():
    """풀에서 커넥션을 가져온다 (컨텍스트 매니저로 사용)."""
    return get_pool().connection()


def close_pool():
    """커넥션 풀을 명시적으로 닫는다."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def build_where_clause(filters: dict | None) -> tuple[str, dict]:
    """필터 dict를 (WHERE 절 문자열, 파라미터 dict)로 변환한다.

    지원 키 형식:
        {"field": value}             → field = %(p_N)s
        {"field__in": [v1, v2]}      → field = ANY(%(p_N)s)   (스칼라 컬럼)
        {"field__overlap": [v1, v2]} → field && %(p_N)s        (배열 컬럼)
    """
    if not filters:
        return "", {}

    clauses = []
    params = {}
    for i, (key, value) in enumerate(filters.items()):
        param_name = f"p_{i}"
        if key.endswith("__in"):
            col = key[:-4]
            clauses.append(f"{col} = ANY(%({param_name})s)")
            params[param_name] = list(value)
        elif key.endswith("__overlap"):
            col = key[:-9]
            clauses.append(f"{col} && %({param_name})s")
            params[param_name] = list(value)
        else:
            clauses.append(f"{key} = %({param_name})s")
            params[param_name] = value

    where = " AND " + " AND ".join(clauses)
    return where, params
