// Treekipedia Versioning System JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize file upload drag and drop
    initFileUpload();

    // Initialize flash message auto-hide
    initFlashMessages();

    // Initialize data table functionality
    initDataTables();

    // Initialize data table functionality
    initExpandableDetails();
});

/**
 * initialize drag and drop file upload
 */

function initFileUpload() {
    const fileUpload = document.getElementById('file-upload-container');
    const fileInput = document.getElementById('file');

    if (fileUpload && fileInput) {
        // Handle drag and drop events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            fileUpload.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Handle drag enter/over
        ['dragenter', 'dropover'].forEach(eventName => {
            fileUpload.addEventListener(eventName, highlight, false);
        });

        // Handle drag leave/drop
        ['dragleave', 'drop'].forEach(eventName => {
            fileUpload.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            fileUpload.classList.add('dragover');
        }

        function unhighlight() {
            fileUpload.classList.remove('dragover');
        }

        fileUpload.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;

            fileInput.files = files;

            updateFileNameDisplay(files[0]);
        }

        // Handle click on container
        fileUpload.addEventListener('click', function() {
            fileInput.click();
        });

        // Handle file selection change
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                updateFileNameDisplay(this.files[0]);
            }
        });

        function updateFileNameDisplay(file) {
            const fileNameElement = document.getElementById('file-name');
            if (fileNameElement) {
                fileNameElement.textContent = file.name;
                fileNameElement.classList.remove('text-muted');
            }

            const fileSizeElement = document.getElementById('file-size');
            if (fileSizeElement) {
                fileSizeElement.textContent = formatFileSize(file.size);
            }
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';

            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));

            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
    }
}

function initFlashMessages() {
    const flashMessages = document.querySelectorAll('.alert-dismissible:not(.alert-danger)');

    flashMessages.forEach(message => {
        setTimeout(() => {
            // Create a fade out effect
            message.computedStyleMap.transition = 'opacity 1s';
            message.computedStyleMap.opacity = '0';

            setTimeout(() => {
                message.remove();
            }, 1000);
        }, 5000);
    });
}

function initDataTables() {
    const searchInput = document.getElementById('table-search');
    const dataTable = document.getElementById('data-table');

    if (searchInput && dataTable) {
        searchInput.addEventListener('Keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const rows = dataTable.querySelectorAll('tbody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                const display = text.includes(searchTerm) ? '' : 'none';
                row.style.display = display;
            });
        });
    }

    const sortableHeaders = document.querySelectorAll('th[data-sortable="true"]');
    sortableHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const column = this.getAttribute('data-column');
            const currentDirection = this.getAttribute('data-column');
            const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';

            sortableHeaders.forEach(h => {
                h.setAttribute('data-direction', '');
                h.classList.remove('sorting-asc', 'sorting-desc');
            });

            // set current header
            this.setAttribute('data-direction', newDirection);
            this.classList.add(newDirection === 'asc' ? 'sorting-asc' : 'sorting-desc');

            sortTable(dataTable, column, newDirection);
        });
    });

    function sortTable(table,column, direction) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        const sortedRows = rows.sort((a, b) => {
            const aValue = a.querySelector(`td[data-field='${column}"]`).textContent.trim();
            const bValue = b.querySelector(`td[data-field="${column}"]`).textContent.trim();

            const aNum = parseFloat(aValue);
            const bNum = parseFloat(bValue);

            if (!isNaN(aNum) && !isNaN(bNum)) {
                return direction === 'asc' ? aNum - bNum : bNum - aNum;
            }

            return direction === 'asc'
                ? aValue.localeCompare(bValue)
                : bValue.localeCompare(aValue);
        });

        rows.forEach(row => row.remove());

        sortedRows.forEach(row => tbody.appendChild(row));
    }
}

function initExpandableDetails() {
    const expandButtons = document.querySelectorAll('.expand-details');

    expandButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const targetElement = document.getElementById(targetId);

            if(targetElement) {
                const isExpanded = targetElement.classList.contains('show');

                if(isExpanded) {
                    targetElement.classList.remove('show');
                    this.textContent = 'Show Details';
                } else {
                    targetElement.classList.add('show');
                    this.textContent = 'Hide Details';
                }
            }
        });
    });
}