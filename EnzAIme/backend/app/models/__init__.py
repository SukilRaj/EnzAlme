"""
backend/app/models/
======================
Reserved for backend-specific ORM/DB models if a database is introduced later
(Section 32 — CSV/Pandas is used for the MVP, SQLite is the natural upgrade
path). The neural network architecture itself lives in the shared
common/enzaime_core/model.py so it can be reused by scripts/06_train_model.py
and the Kaggle notebook without duplicating code.
"""
