function fetchMessage() {
    fetch('/hello_world')
    .then(response => response.json())
    .then(data => {
        document.getElementById('output').innerText = data.message;
    })
    .catch(error => console.error('Error', error));
}