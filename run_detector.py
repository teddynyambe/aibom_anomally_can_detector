import can
import joblib
import pandas as pd

ADDRESS_CLAIM_PGN = 0x00EE00
FEATURE_COLUMNS = ["source_address", "is_zero_name", "timestamp"]


def decode_j1939_pgn(can_id: int) -> int:
    """
    Decode the J1939 PGN from a 29-bit extended CAN identifier.

    For PDU1 messages where PF < 240, the destination address is not
    part of the PGN and must be zeroed. For PDU2 messages where PF >= 240,
    the group extension is part of the PGN.
    """
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF

    if pf < 240:
        return pf << 8

    return (pf << 8) | ps


def build_feature_frame(source_address: int, is_zero_name: int, timestamp: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        [[source_address, is_zero_name, timestamp]],
        columns=FEATURE_COLUMNS,
    )


model = joblib.load("model.joblib")

# bus = can.Bus(interface="socketcan", channel="can0")
bus = can.Bus(

    interface="socketcan",

    channel="can0",

    receive_own_messages=True

)

print("Listening on CAN...")
print("Only PGN 0x00EE00 Address Claimed messages will be evaluated. Other CAN traffic is ignored.")

for msg in bus:
    can_id = msg.arbitration_id
    data = msg.data.hex().upper()
    pgn = decode_j1939_pgn(can_id)
    source_address = can_id & 0xFF

    # Ignore unrelated CAN/J1939 traffic. Without this filter, the model will
    # try to classify every frame on the bus as an address-claim event.
    if pgn != ADDRESS_CLAIM_PGN:
        print(
            f"IGNORED non-address-claim: PGN=0x{pgn:06X} {can_id:08X}#{data}")
        continue

    is_zero_name = 1 if data == "0000000000000000" else 0
    features = build_feature_frame(source_address, is_zero_name)

    prediction = model.predict(features)

    if prediction[0] == 1:
        print(
            f"\033[91mADDRESS-CLAIM ANOMALY: SA=0x{source_address:02X} {can_id:08X}#{data}\033[0m")
    else:
        print(
            f"OK address claim: SA=0x{source_address:02X} {can_id:08X}#{data}")
