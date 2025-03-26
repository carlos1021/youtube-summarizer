let sessionId = null;
let videoUrl = null;

document.getElementById('search-form').addEventListener('submit', async function (event) {
    event.preventDefault();
    const topic = document.getElementById('topic').value;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('chat-container').style.display = 'none';
    document.getElementById('video-container').innerHTML = '';
    document.getElementById('chat-response').innerText = '';

    try {
        const response = await fetch('https://youtube-summarizer-vi8d.onrender.com/build_vectorstore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });

        const data = await response.json();
        if (data.session_id && data.video_url) {
            sessionId = data.session_id;
            videoUrl = data.video_url;

            const embedId = videoUrl.split('v=')[1];
            document.getElementById('video-container').innerHTML = `
                <p>Source: <a href="${videoUrl}" target="_blank">${videoUrl}</a></p>
                <iframe width="100%" height="360" src="https://www.youtube.com/embed/${embedId}" frameborder="0" allowfullscreen></iframe>
            `;

            document.getElementById('chat-container').style.display = 'block';
        } else {
            alert(data.error || 'Something went wrong while building the vectorstore.');
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
});

document.getElementById('ask-button').addEventListener('click', async function () {
    const question = document.getElementById('question').value;
    if (!sessionId || !question) return;

    document.getElementById('chat-response').innerText = 'Thinking... 🤔';

    try {
        const response = await fetch('https://youtube-summarizer-vi8d.onrender.com/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, question })
        });

        const data = await response.json();
        document.getElementById('chat-response').innerText = data.answer || 'No answer found.';
    } catch (err) {
        document.getElementById('chat-response').innerText = 'Error: ' + err.message;
    }
});