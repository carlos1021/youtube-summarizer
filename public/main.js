document.getElementById('predict-button').addEventListener('click', async function (event) {
    event.preventDefault();
    const query = document.getElementById('query').value;
    try {
        const response = await fetch('https://youtube-summarizer-vi8d.onrender.com/generate_random_number', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
        });
        
        console.log('Received some response');
        const data = await response.json();
        console.log('The response is as follows');
        console.log(data);

        document.getElementById('uploadMessage').innerText = data.transcript || "No transcript available.";
    } catch (error) {
        console.error('Error occurred while fetching data:', error);
        document.getElementById('uploadMessage').innerText = "An error occurred. Please try again.";
    }
});
