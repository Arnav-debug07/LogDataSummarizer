document.getElementById('file-upload').addEventListener('change', function(e) {
    const statusDiv = document.getElementById('upload-status');
    if (e.target.files.length > 0) {
        statusDiv.innerHTML = `<span style="color:var(--primary-blue)">Selected: ${e.target.files[0].name}</span>`;
    } else {
        statusDiv.innerHTML = '';
    }
});

async function uploadFile() {
    const fileInput = document.getElementById('file-upload');
    const statusDiv = document.getElementById('upload-status');
    const btn = document.getElementById('upload-btn');
    
    if (fileInput.files.length === 0) {
        statusDiv.innerHTML = '<span style="color:red">Please choose a file first.</span>';
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    btn.disabled = true;
    btn.innerHTML = 'PROCESSING...';
    statusDiv.innerHTML = '';

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (response.ok) {
            statusDiv.innerHTML = `<span style="color:green">${data.message}</span>`;
        } else {
            statusDiv.innerHTML = `<span style="color:red">${data.error}</span>`;
        }
    } catch (err) {
        statusDiv.innerHTML = `<span style="color:red">An error occurred during upload.</span>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'UPLOAD';
    }
}

function promptInteractive() {
    const container = document.getElementById('interactive-container');
    container.classList.toggle('hidden');
    if (!container.classList.contains('hidden')) {
        document.getElementById('query-input').focus();
    }
}

async function runAction(action) {
    doAction(action, '');
}

async function runInteractive() {
    const queryInput = document.getElementById('query-input').value;
    if (!queryInput) {
        alert("Please enter a query");
        return;
    }
    doAction('interactive_summary', queryInput);
}

async function doAction(action, query = '') {
    const resultSec = document.getElementById('result-section');
    const resultContent = document.getElementById('result-content');
    
    resultSec.classList.remove('hidden');
    resultContent.innerHTML = 'Processing your request... (This may take 10-30 seconds)';
    resultSec.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const response = await fetch('/api/action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ action: action, query: query })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            resultContent.innerHTML = `<span style="color:red">Error: ${data.error || 'Unknown error'}</span>`;
            return;
        }

        if (data.type === 'image') {
            resultContent.innerHTML = `<img src="${data.url}" alt="Graphical Summary">`;
        } else if (data.type === 'text') {
            const htmlContent = marked.parse(data.content);
            resultContent.innerHTML = htmlContent;
        }

        setTimeout(() => {
            resultSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);

    } catch (err) {
        resultContent.innerHTML = `<span style="color:red">Failed to connect to the backend server.</span>`;
    }
}
