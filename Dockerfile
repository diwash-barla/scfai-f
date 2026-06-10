# हल्का और सुरक्षित पाइथन बेस इमेज इस्तेमाल करें
FROM python:3.11-slim

# हगिंग फेस के लिए एक नया यूज़र (UID 1000) बनाएँ
RUN useradd -m -u 1000 user

# वर्किंग डायरेक्टरी सेट करें
WORKDIR /app

# पहले requirements कॉपी करें और डिपेंडेंसी इंस्टॉल करें
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# अब एप्लीकेशन की बाकी फाइलें कॉपी करें
COPY app.py .
COPY engine.py .
COPY index.html .

# डायरेक्टरी की ओनरशिप नए यूज़र को दें
RUN chown -R user:user /app

# यूज़र स्विच करें (हगिंग फेस सुरक्षा नियमों के लिए)
USER user

# हगिंग फेस डिफ़ॉल्ट पोर्ट 7860 का उपयोग करता है
EXPOSE 7860

# Gunicorn को पोर्ट 7860 पर रन करें (timeout 120 सेकंड रखा है ताकि API रिक्वेस्ट बीच में न टूटें)
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "4", "--timeout", "120", "app:app"]