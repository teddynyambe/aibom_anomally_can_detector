import can
import joblib

model = joblib.load("model.joblib")

bus = can.Bus(interface="socketcan", channel="can0")

print("Listening on CAN...")

for msg in bus:
    can_id = msg.arbitration_id
    data = msg.data.hex().upper()

    source_address = can_id & 0xFF
    is_zero_name = 1 if data == "0000000000000000" else 0

    features = [[source_address, is_zero_name, 0]]

    prediction = model.predict(features)

    if prediction[0] == 1:
        print(f"🚨 ANOMALY detected: {can_id:08X}#{data}")
    else:
        print(f"OK: {can_id:08X}")
