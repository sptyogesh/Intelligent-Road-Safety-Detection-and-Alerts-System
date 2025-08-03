$(document).ready(function () {
    let uploadedFiles = [];
    let latitude = null;
    let longitude = null;

    // Initialize event listeners
    initEventListeners();

    function initEventListeners() {
        $('#share_location').on('click', getLocation);
        $('#event_images').on('change', handleFileUpload);
        $('#dragDropArea').on('click', () => $('#event_images').click());
        $('#previewBtn').on('click', showPreviewModal);
        $('#submitBtn').on('click', submitForm);
        $('#cancelBtn').on('click', cancelForm);
        $('#previewBody').on('click', '.remove-file', removeFilePreview);
        $('#eventForm input, #eventForm textarea, #eventForm select').on('input change focus blur', checkPreviewButton);
    }

    function getLocation() {
        const button = $(this);
        button.prop('disabled', true).text('Getting Location...');

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                position => {
                    latitude = position.coords.latitude;
                    longitude = position.coords.longitude;
                    button.removeClass('btn-primary').addClass('btn-success').text('Location Retrieved');
                },
                handleGeolocationError
            );
        } else {
            handleGeolocationError({ code: 0 });
        }
    }

    function handleGeolocationError(error) {
        const button = $('#share_location');
        button.prop('disabled', false).text('Get Location');

        switch (error.code) {
            case error.PERMISSION_DENIED:
                alert('Location access denied. Please enable location services.');
                break;
            case error.POSITION_UNAVAILABLE:
                alert('Location information is unavailable.');
                break;
            case error.TIMEOUT:
                alert('The request to get your location timed out.');
                break;
            default:
                alert('An unknown error occurred.');
        }
    }

    function handleFileUpload() {
        const files = Array.from(this.files);
        uploadedFiles = uploadedFiles.concat(files);
        validateFiles();
        displayPreview();
    }

    function validateFiles() {
        const fileError = $('#fileError');
        const fileStatus = $('#fileStatus');
        fileError.hide();
        fileStatus.hide();

        if (uploadedFiles.length < 2) {
            showError(fileError, 'Please upload at least 2 files.');
            return;
        }

        if (uploadedFiles.length > 6) {
            uploadedFiles = uploadedFiles.slice(0, 6);
            showError(fileError, 'You can only upload a maximum of 6 files.');
        }

        const validTypes = ['image/jpeg', 'image/png', 'image/jpg', 'video/mp4'];
        const invalidFiles = uploadedFiles.filter(file => !validTypes.includes(file.type));

        if (invalidFiles.length > 0) {
            uploadedFiles = uploadedFiles.filter(file => validTypes.includes(file.type));
            showError(fileError, 'Invalid file types detected. Please upload only images or mp4 videos.');
        }

        fileStatus.text(`Uploaded ${uploadedFiles.length} file(s).`).show();
        $('#previewBtn').prop('disabled', uploadedFiles.length < 2);
    }

    function showError(element, message) {
        element.text(message).show();
    }

    function displayPreview() {
        const previewContainer = $('#previewBody');
        previewContainer.empty();

        if (uploadedFiles.length > 0) {
            let filesContent = '<div class="preview-container">';
            uploadedFiles.forEach((file, index) => {
                const fileURL = URL.createObjectURL(file);
                filesContent += `
                    <div class="file-preview position-relative" id="file-${index}">
                        ${file.type.startsWith('image/') 
                            ? `<img src="${fileURL}" class="preview-image" alt="Uploaded Image">`
                            : `<video controls class="preview-video"><source src="${fileURL}" type="${file.type}">Your browser does not support the video tag.</video>`}
                        <span class="remove-file" data-index="${index}">&times;</span>
                    </div>`;
            });
            filesContent += '</div>';
            previewContainer.append(filesContent);
        }
    }

    function removeFilePreview() {
        const index = $(this).data('index');
        uploadedFiles.splice(index, 1);
        displayPreview();
        validateFiles();
        checkPreviewButton();
    }

    function validateAllFields() {
        let isValid = true;
        $('#eventForm input[required], #eventForm textarea[required], #eventForm select[required]').each(function () {
            const $input = $(this);
            if (!$input[0].checkValidity()) {
                isValid = false;
            }
        });

        if (!latitude || !longitude) {
            isValid = false;
        }

        return isValid;
    }

    function checkPreviewButton() {
        const allFieldsValid = validateAllFields();
        const minimumFilesUploaded = uploadedFiles.length >= 2;
        $('#previewBtn, #submitBtn').prop('disabled', !(allFieldsValid && minimumFilesUploaded));
    }

    function showPreviewModal() {
        if (!validateAllFields()) {
            alert('Please ensure all fields, including location, are filled out.');
            return;
        }

        $('#previewName').text($('#name').val());
        $('#previewPhone').text($('#phone').val());
        $('#previewState').text($('#state option:selected').text());
        $('#previewDistrict').text($('#district option:selected').text());
        $('#previewSubdivision').text($('#subdivision option:selected').text());
        $('#previewPincode').text($('#pincode').val());
        $('#previewStreet').text($('#street').val());
        $('#previewLatitude').text(latitude || 'Not Provided');
        $('#previewLongitude').text(longitude || 'Not Provided');
        $('#previewMessage').text($('#message').val());

        displayExistingPreviews();
        $('#previewModal').modal('show');
    }

    function displayExistingPreviews() {
        const previewContainer = $('#previewFilesContainer');
        previewContainer.empty();

        if (uploadedFiles.length > 0) {
            uploadedFiles.forEach((file, index) => {
                const fileURL = URL.createObjectURL(file);
                const mediaElement = file.type.startsWith('image/')
                    ? `<img src="${fileURL}" class="preview-image" alt="Uploaded Image">`
                    : `<video controls class="preview-video"><source src="${fileURL}" type="${file.type}">Your browser does not support the video tag.</video>`;
                
                const removeButton = `<button class="btn-remove remove-file" data-index="${index}">X</button>`;
                previewContainer.append(`
                    <div class="file-preview">
                        ${mediaElement}
                        ${removeButton}
                    </div>
                `);
            });
        }
    }

    $('#previewFilesContainer').on('click', '.remove-file', function () {
        const index = $(this).data('index');
        uploadedFiles.splice(index, 1);
        displayExistingPreviews();
        validateFiles();
        checkPreviewButton();
    });

    function resetForm() {
        uploadedFiles = [];
        $('#eventForm')[0].reset();
        $('#previewBody').empty();
        $('#previewModal').modal('hide');
        $('#fileStatus').hide();
        $('#previewBtn').prop('disabled', true);
    }

    function cancelForm() {
        if (confirm('Are you sure you want to cancel? All data will be lost.')) {
            resetForm();
        }
    }

    // Phone number input validation
    document.getElementById('phone').addEventListener('input', function (e) {
        var x = e.target.value.replace(/\D/g, '');
        if (x.length > 0 && !/^[6789]/.test(x)) {
            x = x.substring(1);
        }
        e.target.value = x.slice(0, 10);
    });

    // Name input validation
    document.getElementById('name').addEventListener('input', function() {
        this.value = this.value.replace(/[^a-zA-Z\s.]/g, '');
    });




    /*const BASE_URL = `${window.location.protocol}//${window.location.hostname}:2000`;*/

    function submitForm() {
        const port = window.location.port ;
        const BASE_URL = `${window.location.protocol}//${window.location.hostname}:${port}`;
    
        if (!validateAllFields()) {
            alert('Please ensure all fields are valid before submitting.');
            return;
        }
    
        const formData = new FormData($('#eventForm')[0]);
        uploadedFiles.forEach(file => formData.append('file', file));
        formData.append('latitude', latitude);
        formData.append('longitude', longitude);
        formData.append('name', $('#name').val());
        formData.append('phone', $('#phone').val());
        formData.append('state', $('#state').val());
        formData.append('district', $('#district').val());
        formData.append('subdivision', $('#subdivision').val());
        formData.append('pincode', $('#pincode').val());
        formData.append('street', $('#street').val());
        formData.append('description', $('#message').val());
    
        console.log("Submitting form data:", formData);
    
        const progressOverlay = document.getElementById('progressOverlay');
        const progressBar = document.getElementById('uploadProgressBar');
        const progressText = document.getElementById('uploadProgressText');
        const cancelBtn = document.getElementById('cancelUploadBtn');
    
        progressOverlay.style.display = 'flex';
        progressBar.style.width = '0%';
        progressText.textContent = '0%';
    
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${BASE_URL}/upload`, true);
    
        xhr.upload.onprogress = function(event) {
            if (event.lengthComputable) {
                const percentComplete = Math.round((event.loaded / event.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = percentComplete + '%';
                progressText.textContent = percentComplete + '%';
            }
        };
    
        xhr.onload = function() {
            if (xhr.status >= 200 && xhr.status < 300) {
                console.log('Success:', xhr.responseText);
                progressOverlay.style.display = 'none';
                window.location.href = "submit";
            } else {
                console.error('Error in response:', xhr.responseText);
                progressOverlay.style.display = 'none';
                window.location.href = "Error-upload";
            }
        };
    
        xhr.onerror = function() {
            console.error('Error during file upload.');
            progressOverlay.style.display = 'none';
        };
    
        // Cancel button functionality
        cancelBtn.onclick = function() {
            xhr.abort(); // Cancel the upload
            progressOverlay.style.display = 'none';
            console.log('Are you want to cancel.');
        };
    
        xhr.send(formData);
    }
    
});

function toggleNav() {
    const navLinks = document.getElementById('nav-links');
    navLinks.classList.toggle('active');
}

