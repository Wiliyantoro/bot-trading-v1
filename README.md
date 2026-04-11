# 🧠 BOT TRADING ARCHITECTURE

---

## 🔹 STRATEGY ENGINE

- AUTO -> breakout + reversal
- BREAKOUT
- REVERSAL
- SWITCH
- POINT (baru)

---

## 🔹 RISK MANAGEMENT

- SL static
- SL dynamic (time-based)
- Break Even:
  - normal
  - dynamic (time-based)
- Trailing:
  - dynamic
  - TP follow

---

## 🔹 ORDER SYSTEM

- pending order
- flip system
- multi-position handling

---

## 🔹 FLOW BOT

1. connect MT5
2. ambil tick
3. cek posisi
4. apply risk management
5. jika tidak ada posisi:
   - jalankan strategy sesuai mode

---

## 🔹 FUTURE DEVELOPMENT (IMPORTANT)

### 🚀 NEXT UPGRADE IDEAS

- ATR trailing
- volatility filter
- AI signal scoring
- news filter
- session filter (London / NY)
- max drawdown protection
- auto strategy switch by performance
