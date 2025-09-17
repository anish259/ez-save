document.getElementById('url-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = document.getElementById('url').value;
    const errorDiv = document.getElementById('error');
    const videoInfo = document.getElementById('video-info');
    const titleH2 = document.getElementById('video-title');
    const formatsList = document.getElementById('formats-list');
    const loading = document.getElementById('loading'); // Reference to loading div
    
    errorDiv.textContent = '';
    videoInfo.style.display = 'none';
    formatsList.innerHTML = '';
    loading.style.display = 'none'; // Ensure loading is hidden initially
    
    try {
        const response = await fetch('/get_formats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `url=${encodeURIComponent(url)}`
        });
        
        const data = await response.json();
        if (data.error) {
            errorDiv.textContent = data.error;
            return;
        }
        
        titleH2.textContent = data.title;
        data.formats.forEach(format => {
            const li = document.createElement('li');
            li.textContent = `${format.resolution} (${format.type}, ${format.size})`;
            
            const downloadBtn = document.createElement('button');
            downloadBtn.type = 'button'; // Change to button to handle click event
            downloadBtn.className = 'download-btn';
            downloadBtn.textContent = 'Download';
            downloadBtn.dataset.itag = format.itag; // Store itag in dataset
            downloadBtn.dataset.type = format.type; // Store type in dataset
            
            li.appendChild(downloadBtn);
            formatsList.appendChild(li);
        });
        
        videoInfo.style.display = 'block';
    } catch (err) {
        errorDiv.textContent = 'An error occurred. Please try again.';
    }
});

// Add event delegation for download buttons
document.getElementById('formats-list').addEventListener('click', async (e) => {
    if (e.target.className === 'download-btn') {
        const url = document.getElementById('url').value;
        const itag = e.target.dataset.itag;
        const type = e.target.dataset.type;
        const loading = document.getElementById('loading');
        const errorDiv = document.getElementById('error');

        errorDiv.textContent = '';
        loading.style.display = 'block'; // Show loading indicator

        try {
            const response = await fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `url=${encodeURIComponent(url)}&itag=${itag}&type=${type}`
            });

            if (!response.ok) throw new Error('Download failed');
            const blob = await response.blob();
            const urlObj = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = urlObj;
            a.download = `video_${itag}.mp4`; // Dynamic filename based on itag
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(urlObj);
        } catch (err) {
            errorDiv.textContent = err.message;
        } finally {
            loading.style.display = 'none'; // Hide loading indicator
        }
    }
});