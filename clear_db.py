#!/usr/bin/env python3
"""
سكريبت بسيط لتفريغ قاعدة البيانات وإعادة تهيئتها بجداول فارغة
"""
from database import clear_database

if __name__ == "__main__":
    print("بدء عملية تفريغ قاعدة البيانات...")
    clear_database()
    print("اكتملت العملية.") 