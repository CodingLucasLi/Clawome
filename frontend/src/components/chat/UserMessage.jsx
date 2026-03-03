export default function UserMessage({ message }) {
  return (
    <div className="chat-msg chat-msg-user">
      <div className="chat-msg-bubble chat-bubble-user">
        {message.content}
      </div>
    </div>
  )
}
