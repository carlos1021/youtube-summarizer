let sessionId = null;
let videoUrl = null;

// Add logs with emojis
function addLog(message) {
  const logContainer = document.getElementById('log-container');
  const p = document.createElement('p');
  p.textContent = message;
  logContainer.appendChild(p);
  logContainer.style.display = 'block';
}

function clearLogs() {
  const logContainer = document.getElementById('log-container');
  logContainer.innerHTML = '';
  logContainer.style.display = 'none';
}

// Add chat bubbles
function addChatMessage(sender, message) {
  const chatHistory = document.getElementById('chat-history');
  const msgDiv = document.createElement('div');
  msgDiv.classList.add('chat-message', sender);
  const span = document.createElement('span');
  span.textContent = message;
  msgDiv.appendChild(span);
  chatHistory.appendChild(msgDiv);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Handle topic search
document.getElementById('search-form').addEventListener('submit', async function (event) {
  event.preventDefault();
  const topic = document.getElementById('topic').value;
  document.getElementById('loading').style.display = 'block';
  document.getElementById('chat-container').style.display = 'none';
  document.getElementById('video-container').innerHTML = '';
  document.getElementById('chat-history').innerHTML = '';
  clearLogs();

  addLog("📥 /build_vectorstore endpoint hit");
  addLog(`📝 Topic received: ${topic}`);
  addLog(`🔍 Searching YouTube for query: ${topic}`);

  try {
    const response = await fetch('https://7d34-75-63-26-115.ngrok-free.app/build_vectorstore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic })
    });

    addLog("📡 Request sent to server.");
    const data = await response.json();

    if (data.session_id && data.video_url) {
      sessionId = data.session_id;
      videoUrl = data.video_url;

      addLog("✅ Session data built and session ID created.");
      const embedId = videoUrl.split('v=')[1];
      document.getElementById('video-container').innerHTML = `
        <p>Source: <a href="${videoUrl}" target="_blank">${videoUrl}</a></p>
        <iframe width="100%" height="360" src="https://www.youtube.com/embed/${embedId}" frameborder="0" allowfullscreen></iframe>
      `;

      document.getElementById('chat-container').style.display = 'block';
      setTimeout(clearLogs, 1500);
    } else {
      alert(data.error || 'Something went wrong while building the vectorstore.');
    }
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    document.getElementById('loading').style.display = 'none';
  }
});

// Handle follow-up questions
document.getElementById('ask-button').addEventListener('click', async function () {
  const question = document.getElementById('question').value;
  if (!sessionId || !question) return;

  addChatMessage("user", question);
  document.getElementById('question').value = '';
  addChatMessage("assistant", "Thinking... 🤔");

  try {
    const response = await fetch('https://7d34-75-63-26-115.ngrok-free.app/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, question })
    });

    const data = await response.json();

    const chatHistory = document.getElementById('chat-history');
    chatHistory.removeChild(chatHistory.lastChild); // Remove "Thinking"

    if (data.error) {
      addChatMessage("assistant", "⚠️ The session has expired or the server was inactive. Please reload the page to start again.");
    } else {
      addChatMessage("assistant", data.answer || 'No answer found.');
    }
  } catch (err) {
    const chatHistory = document.getElementById('chat-history');
    chatHistory.removeChild(chatHistory.lastChild);
    addChatMessage("assistant", "❌ Error reaching the server. Please try again.");
  }
});

