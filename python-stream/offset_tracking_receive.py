import asyncio
import signal

from rstream import (
    AMQPMessage,
    Consumer,
    ConsumerOffsetSpecification,
    MessageContext,
    OffsetNotFound,
    OffsetType,
    ServerError,
    StreamDoesNotExist,
    amqp_decoder,
)

cont = 0
first_offset = 0
last_offset = -1
lock = asyncio.Lock()
STREAM = "stream-offset-tracking-python"


async def on_message(msg: AMQPMessage, message_context: MessageContext):
    global cont
    global lock
    global first_offset
    global last_offset

    consumer = message_context.consumer
    stream = await message_context.consumer.stream(message_context.subscriber_name)
    offset = message_context.offset

    if offset == first_offset:
        print(
            "First message received: {} from stream {}, offset {}".format(
                msg, stream, offset
            )
        )

    # store the offset after every 10 messages received
    cont = cont + 1

    if cont % 10 == 0:
        await consumer.store_offset(
            stream=stream,
            offset=offset,
            subscriber_name=message_context.subscriber_name,
        )

    if "marker" in str(msg):
        await consumer.store_offset(
            stream=stream,
            offset=offset,
            subscriber_name=message_context.subscriber_name,
        )
        last_offset = offset


async def consume():
    consumer = Consumer(
        host="localhost",
        port=5552,
        username="guest",
        password="guest",
    )
    await consumer.start()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(
        signal.SIGINT, lambda: asyncio.create_task(consumer.close())
    )
    print("Starting consuming Press control +C to close")
    global first_offset
    first_offset = 0
    try:
        # will raise an exception if store_offset wasn't invoked before
        first_offset = await consumer.query_offset(
            stream=STREAM, subscriber_name="subscriber_1"
        )
    except OffsetNotFound as offset_exception:
        print(f"Offset not previously stored: {offset_exception}")

    except StreamDoesNotExist as stream_exception:
        print(f"Stream does not exist: {stream_exception}")
        exit(1)

    except ServerError as server_error:
        print(f"Server error: {server_error}")
        exit(1)

    # if no offset was previously stored start from the first offset
    await consumer.subscribe(
        stream=STREAM,
        subscriber_name="subscriber_1",
        callback=on_message,
        decoder=amqp_decoder,
        offset_specification=ConsumerOffsetSpecification(
            OffsetType.OFFSET, first_offset
        ),
    )
    await consumer.run()
    # give time to the consumer task to close the consumer
    print(
        "Done consuming first_offset: "
        + str(first_offset)
        + " last_offset: "
        + str(last_offset)
    )
    await asyncio.sleep(1)


asyncio.run(consume())
