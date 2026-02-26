# 🗄️ Database Demo - Quick Start Guide

## 📁 Demo Location
All database demo scripts are now located in the `demo/` folder.

## 🚀 Quick Start

### 1. **Full Database Demo** (Recommended)
```bash
python demo/demo_db.py
```
Shows: Complete database structure, sample data, relationships, and business queries.

### 2. **Quick Overview**
```bash
python demo/quick_view.py
```
Shows: Table names, record counts, and sample data.

### 3. **Start API Server**
```bash
uvicorn app.main:app --reload
```
Visit: http://localhost:8000/docs

## 📊 What You'll See

- **3 Tables**: users, tickets, feedback
- **Sample Data**: Realistic support scenarios
- **AI Classification**: Intent and confidence scores
- **Relationships**: Foreign key constraints
- **Business Queries**: Analytics examples

## 📖 Full Documentation
See `demo/README.md` for comprehensive documentation.

## 🎯 Task 1.6 Status
✅ **COMPLETE** - All database tables created, tested, and documented.
✅ **Branch**: `feat/task1.6` - https://github.com/Yad4o/SRS/tree/feat/task1.6
