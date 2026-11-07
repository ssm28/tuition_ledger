-- Generated from schema.py. Tables are listed parents first.
CREATE TABLE term (
  term_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  invoice_due_days INTEGER NOT NULL
);

CREATE TABLE program (
  program_id TEXT PRIMARY KEY,
  program_code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  level TEXT NOT NULL CHECK (level IN ('UG', 'PG'))
);

CREATE TABLE student (
  student_id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  date_of_birth TEXT NOT NULL,
  program_id TEXT NOT NULL,
  admission_date TEXT NOT NULL,
  cgpa NUMERIC NOT NULL,
  family_income_band TEXT NOT NULL CHECK (family_income_band IN ('LOW', 'MIDDLE', 'HIGH')),
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'WITHDRAWN', 'GRADUATED')),
  FOREIGN KEY (program_id) REFERENCES program(program_id)
);

CREATE TABLE fee_schedule (
  fee_schedule_id TEXT PRIMARY KEY,
  program_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  fee_type TEXT NOT NULL CHECK (fee_type IN ('TUITION', 'LAB', 'LIBRARY', 'TECHNOLOGY', 'ACTIVITY')),
  amount NUMERIC NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
  FOREIGN KEY (program_id) REFERENCES program(program_id),
  FOREIGN KEY (term_id) REFERENCES term(term_id)
);

CREATE TABLE enrollment (
  enrollment_id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  program_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ENROLLED', 'WITHDRAWN', 'COMPLETED', 'CANCELLED')),
  enrolled_on TEXT NOT NULL,
  withdrawn_on TEXT,
  FOREIGN KEY (student_id) REFERENCES student(student_id),
  FOREIGN KEY (program_id) REFERENCES program(program_id),
  FOREIGN KEY (term_id) REFERENCES term(term_id)
);

CREATE TABLE eligibility (
  eligibility_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  min_cgpa NUMERIC NOT NULL,
  max_income_band TEXT CHECK (max_income_band IN ('LOW', 'MIDDLE', 'HIGH')),
  program_id TEXT,
  award_type TEXT NOT NULL CHECK (award_type IN ('PERCENT_OF_TUITION', 'FIXED_AMOUNT')),
  award_value NUMERIC NOT NULL,
  max_award_amount NUMERIC NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  FOREIGN KEY (program_id) REFERENCES program(program_id)
);

CREATE TABLE invoice (
  invoice_id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  enrollment_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  issue_date TEXT NOT NULL,
  due_date TEXT NOT NULL,
  currency TEXT NOT NULL CHECK (currency IN ('INR')),
  total_amount NUMERIC NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ISSUED', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'CANCELLED')),
  FOREIGN KEY (student_id) REFERENCES student(student_id),
  FOREIGN KEY (enrollment_id) REFERENCES enrollment(enrollment_id),
  FOREIGN KEY (term_id) REFERENCES term(term_id)
);

CREATE TABLE scholarship (
  scholarship_id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  eligibility_id TEXT NOT NULL,
  term_id TEXT NOT NULL,
  award_amount NUMERIC NOT NULL,
  awarded_on TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('AWARDED', 'APPLIED', 'REVOKED')),
  FOREIGN KEY (student_id) REFERENCES student(student_id),
  FOREIGN KEY (eligibility_id) REFERENCES eligibility(eligibility_id),
  FOREIGN KEY (term_id) REFERENCES term(term_id)
);

CREATE TABLE invoice_line (
  invoice_line_id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL,
  line_type TEXT NOT NULL CHECK (line_type IN ('TUITION', 'LAB', 'LIBRARY', 'TECHNOLOGY', 'ACTIVITY', 'LATE_FEE', 'SCHOLARSHIP_CREDIT', 'WAIVER')),
  fee_schedule_id TEXT,
  scholarship_id TEXT,
  description TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  line_date TEXT NOT NULL,
  FOREIGN KEY (invoice_id) REFERENCES invoice(invoice_id),
  FOREIGN KEY (fee_schedule_id) REFERENCES fee_schedule(fee_schedule_id),
  FOREIGN KEY (scholarship_id) REFERENCES scholarship(scholarship_id)
);

CREATE TABLE payment (
  payment_id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  payment_date TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  method TEXT NOT NULL CHECK (method IN ('UPI', 'CARD', 'NET_BANKING', 'BANK_TRANSFER', 'CASH')),
  reference TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('POSTED', 'REVERSED')),
  FOREIGN KEY (student_id) REFERENCES student(student_id)
);

CREATE TABLE payment_allocation (
  allocation_id TEXT PRIMARY KEY,
  payment_id TEXT NOT NULL,
  invoice_line_id TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  allocated_on TEXT NOT NULL,
  FOREIGN KEY (payment_id) REFERENCES payment(payment_id),
  FOREIGN KEY (invoice_line_id) REFERENCES invoice_line(invoice_line_id)
);

CREATE TABLE refund (
  refund_id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  payment_id TEXT NOT NULL,
  enrollment_id TEXT,
  reason TEXT NOT NULL CHECK (reason IN ('WITHDRAWAL', 'CANCELLATION', 'OVERPAYMENT')),
  amount NUMERIC NOT NULL,
  requested_on TEXT NOT NULL,
  processed_on TEXT,
  status TEXT NOT NULL CHECK (status IN ('REQUESTED', 'APPROVED', 'PAID', 'REJECTED')),
  FOREIGN KEY (student_id) REFERENCES student(student_id),
  FOREIGN KEY (payment_id) REFERENCES payment(payment_id),
  FOREIGN KEY (enrollment_id) REFERENCES enrollment(enrollment_id)
);

CREATE TABLE ledger_entry (
  ledger_entry_id TEXT PRIMARY KEY,
  event_seq INTEGER NOT NULL UNIQUE,
  student_id TEXT NOT NULL,
  entry_date TEXT NOT NULL,
  entry_type TEXT NOT NULL CHECK (entry_type IN ('CHARGE', 'SCHOLARSHIP_CREDIT', 'WAIVER', 'LATE_FEE', 'PAYMENT', 'REFUND', 'REVERSAL')),
  amount NUMERIC NOT NULL,
  source_table TEXT NOT NULL,
  source_id TEXT NOT NULL,
  FOREIGN KEY (student_id) REFERENCES student(student_id)
);

CREATE TABLE status_event (
  event_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK (entity_type IN ('enrollment', 'invoice', 'scholarship', 'payment', 'refund')),
  entity_id TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT NOT NULL,
  event_date TEXT NOT NULL
);
