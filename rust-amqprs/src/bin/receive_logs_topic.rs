use amqprs::{
    connection::{Connection, OpenConnectionArguments},
    callbacks::{DefaultConnectionCallback, DefaultChannelCallback},
    channel::{QueueDeclareArguments, BasicConsumeArguments, BasicAckArguments, QueueBindArguments, ExchangeDeclareArguments}
};
use tokio::{io::Error as TError, sync::Notify};

#[tokio::main]
async fn main() -> Result<(), Box<TError>> {
    let binding_keys: Vec<_> = std::env::args().skip(1).collect();
    if binding_keys.is_empty() {
        eprintln!(
            "Usage: {} [binding_key]...\n",
            std::env::args().next().unwrap_or_else(|| "receive-topic".into())
        );
        std::process::exit(1);
    }    
    
    let conn = Connection::open(&OpenConnectionArguments::new(
        "localhost",
        5672,
        "guest",
        "guest")).await.unwrap();
    conn.register_callback(DefaultConnectionCallback).await.unwrap();

    let ch = conn.open_channel(None).await.unwrap();
    ch.register_callback(DefaultChannelCallback).await.unwrap();

    let x_name = "topic_logs";
    let x_type = "topic";
    let x_args = ExchangeDeclareArguments::new(x_name, x_type).durable(true).finish();
    ch.exchange_declare(x_args).await.unwrap();    
    
    let q_args = QueueDeclareArguments::new("").durable(false).exclusive(true).finish();
    let (q_name, _, _) = ch.queue_declare(q_args).await.unwrap().unwrap();
    
    for bk in binding_keys {
        ch.queue_bind(QueueBindArguments::new(&q_name, &x_name, &bk)).await.unwrap();
    }

    let consumer_args = BasicConsumeArguments::default().queue(String::from(q_name)).finish();
    let (_ctag, mut rx) = ch.basic_consume_rx(consumer_args).await.unwrap();

    println!(" [*] Waiting for logs. To exit press CTRL+C");

    tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            if let Some(payload) = msg.content {
                println!(" [x] Received {:?}", std::str::from_utf8(&payload).unwrap());

                ch.basic_ack(BasicAckArguments::new(msg.deliver.unwrap().delivery_tag(), false)).await.unwrap();
            }
        }
    });

    let guard = Notify::new();
    guard.notified().await;

    Ok(())
}