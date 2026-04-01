-- ============================================
-- EMPLOYEE MANAGEMENT SYSTEM v2 - DATABASE
-- ============================================

CREATE DATABASE IF NOT EXISTS employee_db;
USE employee_db;

CREATE TABLE IF NOT EXISTS departments (
    dept_id     INT AUTO_INCREMENT PRIMARY KEY,
    dept_name   VARCHAR(100) NOT NULL UNIQUE,
    location    VARCHAR(100),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS designations (
    designation_id  INT AUTO_INCREMENT PRIMARY KEY,
    title           VARCHAR(100) NOT NULL UNIQUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employees (
    emp_id          INT AUTO_INCREMENT PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    email           VARCHAR(100) NOT NULL UNIQUE,
    phone           VARCHAR(20),
    salary          DECIMAL(10, 2) DEFAULT 0.00,
    hire_date       DATE,
    dept_id         INT,
    designation_id  INT,
    status          ENUM('Active', 'Inactive', 'On Leave') DEFAULT 'Active',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id) ON DELETE SET NULL,
    FOREIGN KEY (designation_id) REFERENCES designations(designation_id) ON DELETE SET NULL
);

-- ─── ATTENDANCE TABLE ────────────────────────
CREATE TABLE IF NOT EXISTS attendance (
    att_id      INT AUTO_INCREMENT PRIMARY KEY,
    emp_id      INT NOT NULL,
    att_date    DATE NOT NULL,
    status      ENUM('Present', 'Absent', 'Late', 'Half Day') DEFAULT 'Present',
    check_in    TIME,
    check_out   TIME,
    notes       VARCHAR(255),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_att (emp_id, att_date),
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id) ON DELETE CASCADE
);

-- ─── PAYROLL TABLE ───────────────────────────
CREATE TABLE IF NOT EXISTS payroll (
    pay_id          INT AUTO_INCREMENT PRIMARY KEY,
    emp_id          INT NOT NULL,
    month           INT NOT NULL,
    year            INT NOT NULL,
    basic_salary    DECIMAL(10,2) DEFAULT 0,
    allowances      DECIMAL(10,2) DEFAULT 0,
    deductions      DECIMAL(10,2) DEFAULT 0,
    net_salary      DECIMAL(10,2) DEFAULT 0,
    paid_date       DATE,
    status          ENUM('Pending', 'Paid') DEFAULT 'Pending',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_pay (emp_id, month, year),
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id) ON DELETE CASCADE
);

-- ─── SAMPLE DATA ─────────────────────────────
INSERT IGNORE INTO departments (dept_name, location) VALUES
('Human Resources', 'Floor 1'),
('Information Technology', 'Floor 2'),
('Finance', 'Floor 3'),
('Marketing', 'Floor 4'),
('Operations', 'Floor 5');

INSERT IGNORE INTO designations (title) VALUES
('Manager'),('Senior Developer'),('Junior Developer'),
('Analyst'),('Designer'),('HR Executive'),('Accountant'),('Team Lead');

INSERT IGNORE INTO employees (first_name, last_name, email, phone, salary, hire_date, dept_id, designation_id, status) VALUES
('Ali', 'Hassan', 'ali.hassan@company.com', '0300-1234567', 85000, '2021-03-15', 2, 2, 'Active'),
('Fatima', 'Khan', 'fatima.khan@company.com', '0301-2345678', 92000, '2020-07-01', 2, 8, 'Active'),
('Ahmed', 'Raza', 'ahmed.raza@company.com', '0302-3456789', 65000, '2022-01-10', 1, 6, 'Active'),
('Sara', 'Malik', 'sara.malik@company.com', '0303-4567890', 78000, '2021-09-20', 3, 7, 'Active'),
('Usman', 'Sheikh', 'usman.sheikh@company.com', '0304-5678901', 55000, '2023-02-14', 4, 4, 'Active'),
('Ayesha', 'Butt', 'ayesha.butt@company.com', '0305-6789012', 70000, '2022-06-05', 2, 3, 'On Leave'),
('Bilal', 'Qureshi', 'bilal.qureshi@company.com', '0306-7890123', 95000, '2019-11-30', 2, 1, 'Active'),
('Zara', 'Ali', 'zara.ali@company.com', '0307-8901234', 60000, '2023-05-01', 4, 5, 'Active');

SELECT 'Database v2 setup complete!' as Status;
