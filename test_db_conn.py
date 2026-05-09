import sqlalchemy

urls = [
    # Transaction pooler port 6543
    "postgresql+psycopg2://postgres.npabvnvlzljonmlvwxev:rsqNeWkY5Ie4ZZyy@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres",
    "postgresql+psycopg2://postgres.npabvnvlzljonmlvwxev:rsqNeWkY5Ie4ZZyy@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres",
    # Session pooler port 5432
    "postgresql+psycopg2://postgres.npabvnvlzljonmlvwxev:rsqNeWkY5Ie4ZZyy@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
    "postgresql+psycopg2://postgres.npabvnvlzljonmlvwxev:rsqNeWkY5Ie4ZZyy@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres",
    # Direct DB port 5432
    "postgresql+psycopg2://postgres:rsqNeWkY5Ie4ZZyy@db.npabvnvlzljonmlvwxev.supabase.co:5432/postgres"
]

for url in urls:
    try:
        print(f"Testing {url}...")
        engine = sqlalchemy.create_engine(url, connect_args={'connect_timeout': 5})
        conn = engine.connect()
        conn.close()
        print(f"SUCCESS: {url}")
        break
    except Exception as e:
        print(f"FAILED: {e}")
        pass
