const backendURL = "https://youtube-summarizer-vi8d.onrender.com";
document.getElementById('upload-client-secret-btn').addEventListener('click', async () => {
    const fileInput = document.getElementById('client-secret-file');
    if (!fileInput.files[0]) {
      alert("Please select a JSON file first.");
      return;
    }

    const formData = new FormData();
    formData.append('client_secret', fileInput.files[0]);

    try {
      const response = await fetch(`${backendURL}/upload_client_secret`, {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      document.getElementById('uploadClientSecretMessage').innerText = data.message || data.error || '';
    } catch (error) {
      document.getElementById('uploadClientSecretMessage').innerText = "Error uploading client secret.";
      console.error(error);
    }
  });

  // 2. Start OAuth
  document.getElementById('start-oauth-btn').addEventListener('click', async () => {
    try {
      const response = await fetch(`${backendURL}/start_oauth`, { method: 'GET' });
      const data = await response.json();
      if (data.error) {
        document.getElementById('oauthMessage').innerText = data.error;
      } else if (data.authorization_url) {
        // Open the authorization URL in new tab/window
        window.open(data.authorization_url, '_blank');
        document.getElementById('oauthMessage').innerText = "OAuth flow started, please complete in new window.";
      }
    } catch (error) {
      document.getElementById('oauthMessage').innerText = "Error initiating OAuth.";
      console.error(error);
    }
  });

  // 3. Check Auth Status
  document.getElementById('check-auth-btn').addEventListener('click', async () => {
    try {
      const response = await fetch(`${backendURL}/check_auth`, { method: 'GET' });
      const data = await response.json();
      document.getElementById('authStatus').innerText =
        data.authenticated ? "Authenticated" : "Not Authenticated";
    } catch (error) {
      document.getElementById('authStatus').innerText = "Error checking auth status.";
      console.error(error);
    }
  });

  // 4. Summarize
  document.getElementById('summarize-btn').addEventListener('click', async () => {
    const query = document.getElementById('queryInput').value.trim();
    if (!query) {
      alert("Please enter a query.");
      return;
    }
    try {
      const response = await fetch(`${backendURL}/get_transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await response.json();
      if (!response.ok) {
        // e.g. 401 error => data.error
        document.getElementById('summaryResult').innerText = data.error || "Error occurred.";
      } else {
        document.getElementById('summaryResult').innerText = data.transcript || "No transcript.";
      }
    } catch (error) {
      document.getElementById('summaryResult').innerText = "Error fetching transcript.";
      console.error(error);
    }
  });