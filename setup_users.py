
import mysql.connector
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345678',   # <-- apna password
    'database': 'employee_db'
}

users = [
    {'username': 'admin',    'password': 'admin123',  'role': 'admin'},
    {'username': 'hr',       'password': 'hr123',     'role': 'hr'},
    {'username': 'employee', 'password': 'emp123',    'role': 'employee'},
]

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

# Create table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id    INT AUTO_INCREMENT PRIMARY KEY,
    username   VARCHAR(50) NOT NULL UNIQUE,
    password   VARCHAR(255) NOT NULL,
    role       ENUM('admin','hr','employee') DEFAULT 'employee',
    emp_id     INT DEFAULT NULL,
    is_active  TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id) ON DELETE SET NULL
)
""")

for u in users:
    hashed = generate_password_hash(u['password'])
    try:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (u['username'], hashed, u['role'])
        )
        print(f"✅ Created user: {u['username']} / {u['password']} ({u['role']})")
    except Exception as e:
        print(f"⚠️  {u['username']} already exists — skipped")

conn.commit()
cursor.close()
conn.close()
print("\n✅ Done! Login credentials:")
print("   Admin:    admin / admin123")
print("   HR:       hr / hr123")
print("   Employee: employee / emp123")
