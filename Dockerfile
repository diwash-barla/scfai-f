# हल्का और सुरक्षित पाइथन बेस इमेज इस्तेमाल करें
FROM python:3.11-slim

# वर्किंग डायरेक्टरी सेट करें
WORKDIR /app

# पहले requirements कॉपी करें और डिपेंडेंसी इंस्टॉल करें (कैश का फायदा उठाने के लिए)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# अब एप्लीकेशन की बाकी फाइलें कॉपी करें
COPY app.py .
COPY engine.py .
COPY index.html .

# पोर्ट 5000 एक्सपोज़ करें (जिस पर हमारा ऐप चलेगा)
EXPOSE 5000

# प्रोडक्शन के लिए Gunicorn का इस्तेमाल करके ऐप को रन करें
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]