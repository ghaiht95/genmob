FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    make \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install SoftEther VPN
RUN wget https://github.com/SoftEtherVPN/SoftEtherVPN_Stable/releases/download/v4.41-9782-beta/softether-vpnserver-v4.41-9782-beta-2022.11.17-linux-x64-64bit.tar.gz \
    && tar xf softether-vpnserver-v4.41-9782-beta-2022.11.17-linux-x64-64bit.tar.gz \
    && cd vpnserver \
    && make \
    && cd .. \
    && mv vpnserver /usr/local/ \
    && rm softether-vpnserver-v4.41-9782-beta-2022.11.17-linux-x64-64bit.tar.gz \
    && chmod 600 /usr/local/vpnserver/* \
    && chmod 700 /usr/local/vpnserver/vpncmd \
    && chmod 700 /usr/local/vpnserver/vpnserver

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ✅ Start app with gunicorn and gevent instead of eventlet
CMD ["gunicorn", "-k", "gevent", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]
