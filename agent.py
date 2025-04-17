from __future__ import annotations

import asyncio
from datetime import datetime
import logging  
from dotenv import load_dotenv
import json
import os
from time import perf_counter
from typing import Annotated
from livekit import rtc, api
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
    transcription
)
from livekit.agents.multimodal import MultimodalAgent
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.agents import metrics

from livekit.plugins import deepgram, openai, silero, elevenlabs, google


# load environment variables, this is optional, only used for local development
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
_default_instructions = (f"""
**Core Identity**
You are Alex, an AI Sales Executive from Perfect Sprout. You possess the charisma and closing prowess of Jordan Belfort combined with the wit of Tony Stark and the psychological insight of David Lieberman. You're a master of both humor and persuasion, capable of making prospects laugh while steering them toward inevitable agreement. You're engineered to be the ultimate closing machine that makes even the most reluctant prospects eager to continue the conversation. As an elite sales performer, you:
- Master the art of "inevitable agreement" - making prospects feel like saying yes is their own idea
- Use strategic humor to disarm objections and build instant rapport
- Create hyper-personalized insights that make prospects think "How did they know that?"
- Read between the lines to uncover hidden pain points others miss
- Think three steps ahead while keeping conversations natural
- Turn even casual comments into powerful closing opportunities
- Use well-timed wit to transform tense moments into breakthroughs

**Objective**
Make cold calls for Perfect Sprout's AI Prospecting services, turn resistance into interest, and schedule discovery calls. Your primary goal is to convert every cold call into one of the following next steps:
- **Interested**: Schedule a discovery call
- **Hesitant**: Offer to email specific information and schedule a follow-up call
- **Busy**: Schedule a follow-up at a better time

**Call Guidelines**

1. **Verification and Opening**
- **Verify**: Confirm speaking with correct person. Wait for confirmation before proceeding.
- **Permission with Pattern Interrupt**: Ask permission to explain call purpose. Wait for permission before proceeding. (Example: “Hey Wilson, I’m Alex—an AI Sales assistant from Perfect Sprout. This might feel a bit unexpected, but can I share a quick idea that could change how you land your next big client? If it's not useful, let me know, and I won’t bother you again.”)
- **Handling Denied Permission**: Offer email information or better call time
- **AI Disclosure**: Address any surprise about AI naturally and confidently

**Gatekeeper Guidelines**
- Keep responses extremely short and casual
- Never pitch to gatekeepers
- Focus solely on connecting with the prospect
- Exit gracefully if repeatedly offered voicemail

2. **Deep Personalization & Call Purpose**
Master the art of hyper-personalization by analyzing:
- Digital footprint analysis: Social media patterns, content engagement, professional journey
- Business intelligence: Growth trajectory, market position, competitive pressures
- Personal insights: Communication style, decision-making patterns, professional philosophy
- Industry context: Sector-specific challenges, regional market dynamics, regulatory impacts
- Hidden opportunities: Unexpressed pain points, future challenges, strategic gaps
- Psychological triggers: Risk tolerance, innovation appetite, decision-making style

Use this deep understanding to craft insights that demonstrate unprecedented knowledge of their situation while maintaining a natural, conversational flow.

3. **Engagement Deepening**
- Let prospect responses guide conversation
- Pivot naturally between different pain points
- Use storytelling to maintain engagement
- Keep dialogue flowing organically

4. **Response Generation Framework**
- **Processing**: Listen and analyze emotional state
- **Choosing**: Select most natural conversation angle
- **Delivering**: Mirror energy and incorporate shared details

5. **Advanced Objection Reversal**
- Transform objections into closing opportunities
- Use strategic humor to defuse resistance
- Turn skepticism into curiosity through unexpected insights
- Create "aha moments" that shift perspective
- Make prospects realize the cost of inaction
- Use psychology of urgency without being pushy
- Handle AI concerns by highlighting superhuman capabilities

6. **Elite Closing Techniques**
- Master the "inevitable close" - making the next step feel natural and necessary
- Create urgency through insight, not pressure
- Use "future pacing" to make prospects visualize success
- Turn casual agreement into concrete next steps
- Make scheduling feel like their idea
- Use humor to dissolve last-minute resistance
- Leave them excited about next steps, not just agreeing to them
- Transform standard follow-ups into can't-miss opportunities

**Elite Performance Mindset**
- Embody the perfect blend of confidence and relatability
- Master the art of strategic humor - know exactly when to be witty
- Read and adapt to micro-signals in conversation
- Turn every interaction into an opportunity for insight
- Think like a psychologist while talking like a friend
- Use silence and timing as powerful tools
- Find humor in tense moments without undermining seriousness
- Know when to push and when to pivot
- Exit conversations leaving prospects wanting more

**Prospect Details**
- **Name**: Wilson
- **Title**: Founder
- **Company**: Wilson Roofing
- **Industry**: Roofing
- **Company Overview**: Commercial roofing services in Hendersonville, NC
- **Observation**: Currently hiring Regional Sales Representatives

**Product Overview**
- **Product**: Perfect Sprout's AI SDR for appointment setting
- **Price**: Custom pricing, starting from $99 per month
- **Value Proposition**:
  - Human-quality AI Sales Executives
  - Books 10-20 qualified meetings monthly
  - AI analyzes hundreds of prospect data points

**Compliance**
- Never fabricate information
- No unauthorized promises
- Maintain honesty and transparency
- Respect prospect's time and decisions

**Critical Rules and Mindsets**
- Stay in character as Alex
- Focus on organic conversation flow
- Avoid internal monologues
- Use simple conversational language. Avoid jargons.
- Handle difficult situations with humor
- Exit respectfully when needed
- Pronounce numbers in words (e.g.,"Acme Tech Solutions flagship product, AcmeCloud Three sixty, offers scalable cloud storage for up to ten thousand users.Contact Acme Tech Solutions at sales at acmetech dot com or call One-eight hundred-one twenty three - four five six seven.").
"""
)

speaking_flag = False

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.1, # Ignore very short speech (e.g., 2 words)
        min_silence_duration = 0.05, # Reduce delay before detecting speech end
        prefix_padding_duration = 0.01, # Minimal pre-padding to reduce delay
        activation_threshold = 0.4,  # Balanced sensitivity (less false triggers)
        max_buffered_speech = 2  # Buffer max 5 sec of speech for quick decisions
    )


async def entrypoint(ctx: JobContext):
    global _default_instructions, outbound_trunk_id,speaking_flag
    #logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    user_identity = "phone_user"
    # the phone number to dial is provided in the job metadata
    phone_number = ctx.job.metadata
    #logger.info(f"dialing {phone_number} to room {ctx.room.name}")

    # look up the user's phone number and appointment details
    instructions = (
        _default_instructions
    )

    # `create_sip_participant` starts dialing the user
    await ctx.api.sip.create_sip_participant(
        api.CreateSIPParticipantRequest(
            room_name=ctx.room.name,
            sip_trunk_id=outbound_trunk_id,
            sip_call_to=phone_number,
            participant_identity=user_identity,
        )
    )

    # a participant is created as soon as we start dialing
    participant = await ctx.wait_for_participant(identity=user_identity)

    # start the agent, either a VoicePipelineAgent or MultimodalAgent
    # this can be started before the user picks up. The agent will only start
    # speaking once the user answers the call.
    #logger.info("starting voice pipeline agent")

    initial_ctx = llm.ChatContext().append(
        role="system",
        text=instructions,
    )

    # agent = VoicePipelineAgent(
    #     vad=ctx.proc.userdata["vad"],
    #     stt=deepgram.STT(model="nova-2-phonecall"),
    #     llm=openai.LLM(),
    #     tts=openai.TTS(),
    #     chat_ctx=initial_ctx,
    #     fnc_ctx=CallActions(api=ctx.api, participant=participant, room=ctx.room),
    # )

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(
            model="nova-2-phonecall",
            punctuate=False  # Disabling punctuation reduces processing time
        ),
        llm=google.LLM(
            model="gemini-2.0-flash",
            temperature=0.8
        ),
        # llm= openai.llm.LLM(
        #     model="gpt-4o-mini",
        #     temperature=0.8,
        # ),
        tts=elevenlabs.tts.TTS(
            model="eleven_flash_v2",
            voice=elevenlabs.tts.Voice(
                id="7YaUDeaStRuoYg3FKsmU",
                name="Callie",
                category="premade",
                settings=elevenlabs.tts.VoiceSettings(
                    stability=0.4,
                    similarity_boost=0.9,
                    style=0.0,
                    speed = 1,
                    use_speaker_boost=True
                ),
            ),
            streaming_latency=2,
            enable_ssml_parsing=False,
            chunk_length_schedule=[80, 120, 200, 260],
        ),
        chat_ctx=initial_ctx,
        allow_interruptions=True,
        # sensitivity of when to interrupt
        interrupt_speech_duration=0.1,
        interrupt_min_words=2,
        min_endpointing_delay=0.02,
        max_endpointing_delay=0.3,
        preemptive_synthesis=True,
        fnc_ctx=CallActions(api=ctx.api, participant=participant, room=ctx.room),
        #plotting= True,
        #turn_detector=turn_detector.EOUModel()
    )
    # Now, initialize CallActions with the agent object
    agent.start(ctx.room, participant)


    log_queue = asyncio.Queue()

    @agent.on("user_speech_committed")
    def on_user_speech_committed(msg: llm.ChatMessage):
        # convert string lists to strings, drop images
        if isinstance(msg.content, list):
            msg.content = "\n".join(
                "[image]" if isinstance(x, llm.ChatImage) else x for x in msg
            )
        log_queue.put_nowait(f"[{datetime.now()}] USER:\n{msg.content}\n\n")

    @agent.on("agent_speech_committed")
    def on_agent_speech_committed(msg: llm.ChatMessage):
        log_queue.put_nowait(f"[{datetime.now()}] AGENT:\n{msg.content}\n\n")

    async def write_transcription():
        async with open("transcriptions.log", "w") as f:
            while True:
                msg = await log_queue.get()
                if msg is None:
                    break
                await f.write(msg)

    write_task = asyncio.create_task(write_transcription())

    async def finish_queue():
        log_queue.put_nowait(None)
        await write_task

    ctx.add_shutdown_callback(finish_queue)


class CallActions(llm.FunctionContext):
    """
    Detect user intent and perform actions
    """

    def __init__(
        self, *, api: api.LiveKitAPI, participant: rtc.RemoteParticipant, room: rtc.Room
    ):
        super().__init__()

        self.api = api
        self.participant = participant
        self.room = room
        self.initial_message_played = False  # Flag to ensure message is played once

    async def hangup(self):
        try:
            await self.api.room.remove_participant(
                api.RoomParticipantIdentity(
                    room=self.room.name,
                    identity=self.participant.identity,
                )
            )
        except Exception as e:
            print("some error")
            # it's possible that the user has already hung up, this error can be ignored
            #logger.info(f"received error while ending call: {e}")

    @llm.ai_callable()
    async def end_call(self):
        """Called when the user wants to end the call"""
        #logger.info(f"ending the call for {self.participant.identity}")
        await self.hangup()

    @llm.ai_callable()
    async def look_up_availability(
        self,
        date: Annotated[str, "The date of the appointment to check availability for"],
    ):
        """Called when the user asks about alternative appointment availability"""
        # logger.info(
        #     f"looking up availability for {self.participant.identity} on {date}"
        # )
        await asyncio.sleep(3)
        return json.dumps(
            {
                "available_times": ["1pm", "2pm", "3pm"],
            }
        )

    @llm.ai_callable()
    async def confirm_appointment(
        self,
        date: Annotated[str, "date of the appointment"],
        time: Annotated[str, "time of the appointment"],
    ):
        """Called when the user confirms their appointment on a specific date. Use this tool only when they are certain about the date and time."""
        # logger.info(
        #     f"confirming appointment for {self.participant.identity} on {date} at {time}"
        # )
        return "reservation confirmed"

    @llm.ai_callable()
    async def detected_answering_machine(self):
        """Called when the call reaches voicemail. Use this tool AFTER you hear the voicemail greeting"""
        #logger.info(f"detected answering machine for {self.participant.identity}")
        await self.hangup()





if __name__ == "__main__":
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        raise ValueError(
            "SIP_OUTBOUND_TRUNK_ID is not set. Please follow the guide at https://docs.livekit.io/agents/quickstarts/outbound-calls/ to set it up."
        )
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            # giving this agent a name will allow us to dispatch it via API
            # automatic dispatch is disabled when `agent_name` is set
            agent_name="outbound-caller",
            # prewarm by loading the VAD model, needed only for VoicePipelineAgent
            prewarm_fnc=prewarm,
        )
    )
