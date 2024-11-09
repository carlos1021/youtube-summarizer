document.getElementById('predict-button').addEventListener('click', async function () {
    const response = await fetch('https://youtube-summarizer-vi8d.onrender.com/generate_random_number', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
        });
        console.log('Received some response');
        const data = await response.json();
        console.log('The response is as follows');
        console.log(data);
    document.getElementById('uploadMessage').innerText = data.random_number;
});

// hello world