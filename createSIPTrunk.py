import asyncio
from dotenv import load_dotenv
import os
from livekit import api
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
# load environment variables, this is optional, only used for local development
load_dotenv(dotenv_path=".env.local")

async def main():
  livekit_api = api.LiveKitAPI()

  trunk = SIPOutboundTrunkInfo(
    name = "twilioLiveKitTrunk",
    address = "jivus-twilio-sip.pstn.twilio.com",
    numbers = ['+18147079806'],
    auth_username = "mikhil-jivus",
    auth_password = 'Devops@111990'
  )

  # trunk = SIPOutboundTrunkInfo(
  #   name="vonageLiveKitTrunk",
  #   address="jivus-mikhil.sip.vonage.com",
  #   numbers=['+12019403660'],
  #   auth_username="jivus-mikhil",
  #   auth_password='6tU!gY##B!pB;3$AM2Gl'
  # )

  # trunk = SIPOutboundTrunkInfo(
  #   name="telynxLiveKitTrunk",
  #   address="sip.telnyx.com",
  #   numbers=['+18446830139'],
  #   auth_username="mikhil11",
  #   auth_password='Devops@111990'
  # )

  request = CreateSIPOutboundTrunkRequest(
    trunk = trunk
  )

  trunk = await livekit_api.sip.create_sip_outbound_trunk(request)

  print(f"Successfully created {trunk}")

  await livekit_api.aclose()

asyncio.run(main())