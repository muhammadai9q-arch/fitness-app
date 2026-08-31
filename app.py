import os
from flask import Flask, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# إعداد قاعدة البيانات
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fitness.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# نموذج جدول الأطعمة في قاعدة البيانات
class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, nullable=False)
    carbs = db.Column(db.Float, nullable=False)
    fat = db.Column(db.Float, nullable=False)
    serving_grams = db.Column(db.Float, default=100.0)

    def to_dict(self):
        return {
            "id": self.id,
            "الاسم": self.name,
            "السعرات الحرارية": self.calories,
            "بروتين": self.protein,
            "الكربوهيدرات": self.carbs,
            "الدهون": self.fat,
            "serving_grams": self.serving_grams
        }

# إنشاء الجداول عند البدء
with app.app_context():
    db.create_all()

# تصميم واجهة التطبيق التفاعلية
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تطبيق التغذية واللياقة</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2e7d32;
            --primary-light: #e8f5e9;
            --primary-dark: #1b5e20;
            --bg: #f8f9fa;
            --card-bg: #ffffff;
            --text-main: #212529;
            --text-muted: #6c757d;
            --border: #e9ecef;
            --shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Cairo', sans-serif; }
        body { background-color: var(--bg); color: var(--text-main); display: flex; justify-content: center; min-height: 100vh; }
        .app-container { width: 100%; max-width: 480px; background-color: var(--card-bg); min-height: 100vh; box-shadow: 0 0 25px rgba(0,0,0,0.08); display: flex; flex-direction: column; }
        header { background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; padding: 24px 20px 20px; border-bottom-left-radius: 24px; border-bottom-right-radius: 24px; }
        .header-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
        .header-title h1 { font-size: 1.4rem; font-weight: 800; }
        .search-container { position: relative; }
        .search-input { width: 100%; padding: 14px 16px; border: none; border-radius: 14px; font-size: 0.95rem; outline: none; }
        .stats-summary { display: flex; gap: 10px; padding: 16px 20px; background-color: var(--primary-light); margin: 16px 20px 0; border-radius: 16px; }
        .stat-item { flex: 1; text-align: center; }
        .stat-val { font-size: 1.1rem; font-weight: 700; color: var(--primary-dark); }
        .stat-label { font-size: 0.75rem; color: var(--text-muted); }
        main { flex: 1; padding: 16px 20px; }
        .food-list { display: flex; flex-direction: column; gap: 12px; }
        .food-card { background-color: white; border: 1px solid var(--border); border-radius: 16px; padding: 16px; box-shadow: var(--shadow); display: flex; justify-content: space-between; align-items: center; }
        .food-name { font-size: 1.05rem; font-weight: 700; margin-bottom: 4px; }
        .food-serving { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 8px; }
        .macros-grid { display: flex; gap: 6px; }
        .macro-chip { font-size: 0.75rem; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
        .macro-p { background-color: #ffebee; color: #c62828; }
        .macro-c { background-color: #e3f2fd; color: #1565c0; }
        .macro-f { background-color: #fff8e1; color: #f57f17; }
        .calories-badge { background-color: var(--primary-light); color: var(--primary-dark); padding: 10px 14px; border-radius: 14px; text-align: center; min-width: 80px; }
        .cal-number { font-size: 1.1rem; font-weight: 800; }
        .cal-unit { font-size: 0.7rem; }
    </style>
</head>
<body>
<div class="app-container">
    <header>
        <div class="header-title">
            <h1>دليل التغذية 🥗</h1>
            <span style="font-size:0.8rem; background:rgba(255,255,255,0.2); padding:4px 10px; border-radius:12px;">أونلاين</span>
        </div>
        <div class="search-container">
            <input type="text" id="searchInput" class="search-input" placeholder="ابحث عن وجبة أو طعام..." oninput="handleSearch()">
        </div>
    </header>

    <div class="stats-summary">
        <div class="stat-item"><div class="stat-val" id="totalItems">0</div><div class="stat-label">عنصر غذائي</div></div>
        <div class="stat-item"><div class="stat-val">100g</div><div class="stat-label">حجم الحصة</div></div>
        <div class="stat-item"><div class="stat-val" style="color: var(--primary);">مضمون 100%</div><div class="stat-label">دقة البيانات</div></div>
    </div>

    <main>
        <div id="foodList" class="food-list">
            <p style="text-align:center; padding:20px; color:#666;">جاري التحميل...</p>
        </div>
    </main>
</div>

<script>
    let allFoods = [];
    async function fetchFoods() {
        try {
            const res = await fetch('/api/foods');
            allFoods = await res.json();
            document.getElementById('totalItems').innerText = allFoods.length;
            renderFoods(allFoods);
        } catch (e) {
            document.getElementById('foodList').innerHTML = '<p style="text-align:center; color:red;">تعذر جلب البيانات</p>';
        }
    }

    function renderFoods(foods) {
        const container = document.getElementById('foodList');
        if (foods.length === 0) {
            container.innerHTML = '<p style="text-align:center; padding:20px;">لا توجد نتائج 🔍</p>';
            return;
        }
        container.innerHTML = foods.map(food => `
            <div class="food-card">
                <div>
                    <div class="food-name">${food['الاسم'] || 'طعام'}</div>
                    <div class="food-serving">لكل ${food['serving_grams'] || 100} جرام</div>
                    <div class="macros-grid">
                        <span class="macro-chip macro-p">بروتين: ${food['بروتين']}g</span>
                        <span class="macro-chip macro-c">كاربس: ${food['الكربوهيدرات']}g</span>
                        <span class="macro-chip macro-f">دهون: ${food['الدهون']}g</span>
                    </div>
                </div>
                <div class="calories-badge">
                    <div class="cal-number">${food['السعرات الحرارية']}</div>
                    <div class="cal-unit">سعرة</div>
                </div>
            </div>
        `).join('');
    }

    function handleSearch() {
        const query = document.getElementById('searchInput').value.toLowerCase().trim();
        renderFoods(allFoods.filter(f => (f['الاسم'] || '').toLowerCase().includes(query)));
    }

    fetchFoods();
</script>
</body>
</html>
'''

# 1. الصفحة الرئيسية (عرض تطبيق الجوال)
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

# 2. رابط جلب البيانات JSON
@app.route('/api/foods', methods=['GET'])
def get_foods():
    foods = Food.query.all()
    return jsonify([f.to_dict() for f in foods])

# 3. رابط تعبئة الأطعمة في قاعدة البيانات
@app.route('/api/seed', methods=['GET'])
def seed():
    if Food.query.first():
        return jsonify({"message": "البيانات موجودة بالفعل!"})
    
    sample_foods = [
        Food(name="صدر دجاج مطبوخ", calories=165, protein=31, carbs=0, fat=3.6),
        Food(name="أرز أبيض مطبوخ", calories=130, protein=2.7, carbs=28, fat=0.3),
        Food(name="بيض مسلوق", calories=155, protein=12.6, carbs=1.1, fat=10.6),
        Food(name="شوفان", calories=389, protein=16.9, carbs=66.3, fat=6.9),
        Food(name="تفاح", calories=52, protein=0.3, carbs=14, fat=0.2),
        Food(name="زيت زيتون", calories=884, protein=0, carbs=0, fat=100),
        Food(name="سمك سلمان مشوي", calories=206, protein=22, carbs=0, fat=12.3),
        Food(name="موز", calories=89, protein=1.1, carbs=23, fat=0.3),
    ]
    db.session.bulk_save_objects(sample_foods)
    db.session.commit()
    return jsonify({"message": "تم إضافة الأطعمة الأولية بنجاح!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


    
