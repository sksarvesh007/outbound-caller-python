import asyncio
import os

from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import CreateSIPParticipantRequest, SIPParticipantInfo
load_dotenv(dotenv_path=".env.local")
SIP_OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")
async def main():
    livekit_api = api.LiveKitAPI()

    request = CreateSIPParticipantRequest(
        sip_trunk_id=SIP_OUTBOUND_TRUNK_ID,
        sip_call_to="+919399661427",
        room_name="my-sip-room",
        participant_identity="sip-test",
        participant_name="Test Caller",
        krisp_enabled=True,
    )

    participant = await livekit_api.sip.create_sip_participant(request)

    print(f"Successfully created {participant}")

    await livekit_api.aclose()


asyncio.run(main())