<?php
/*
 * Combined PHP Proxy Script for Multiple Flask API Servers
 * Place this in public_html/api/index.php
 * 
 * This script routes requests to different Flask servers based on the URL path:
 * - /api/download-and-analyze-vision -> localhost:5001 (Drive-Airtable server)
 * - /api/rename-file -> localhost:5001 (Drive-Airtable server)
 * - /api/health -> localhost:5001 (Drive-Airtable server)
 * - /api/temp-files -> localhost:5001 (Drive-Airtable server)
 * - /api/cleanup -> localhost:5001 (Drive-Airtable server)
 * 
 * To add more servers, update the $endpoint_routing array below
 */

// ============================================
// CONFIGURATION: Add your Flask servers here
// ============================================
$endpoint_routing = [
    // Drive-Airtable Flask Server (port 5001)
    'download-and-analyze-vision' => 'http://127.0.0.1:5001',
    'rename-file' => 'http://127.0.0.1:5001',
    'temp-files' => 'http://127.0.0.1:5001',
    'cleanup' => 'http://127.0.0.1:5001',
    'download-and-analyze' => 'http://127.0.0.1:5001',
    
    // Tranzila-Airtable Flask Server (port 2000)
    'health' => 'http://127.0.0.1:2000',
    'test-auth' => 'http://127.0.0.1:2000',
    'docs' => 'http://127.0.0.1:2000',
    'create-payment-request' => 'http://127.0.0.1:2000',
    'process-direct-transaction' => 'http://127.0.0.1:2000',
    'webhook/payment-status' => 'http://127.0.0.1:2000',
    'webhook/transaction-update' => 'http://127.0.0.1:2000',
    'create-document' => 'http://127.0.0.1:2000',
    'get-document' => 'http://127.0.0.1:2000',
    'get-documents' => 'http://127.0.0.1:2000',
    'create-manual-invoice' => 'http://127.0.0.1:2000',
];

header('Content-Type: application/json');

// CORS headers if needed
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

// Handle OPTIONS preflight requests
if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    exit(0);
}

// Get the request path
$request_path = $_SERVER['REQUEST_URI'];
$path_parts = explode('/', trim($request_path, '/'));

// Extract the endpoint (everything after /api/)
$endpoint = '';
if (count($path_parts) > 1 && $path_parts[0] === 'api') {
    $endpoint = implode('/', array_slice($path_parts, 1));
}

// Handle nested paths (e.g., webhook/payment-status)
$matched_endpoint = null;
foreach ($endpoint_routing as $route => $server) {
    if (strpos($endpoint, $route) === 0) {
        $matched_endpoint = $route;
        break;
    }
}

// Route to appropriate Flask server based on endpoint
if ($matched_endpoint) {
    $flask_base_url = $endpoint_routing[$matched_endpoint];
} else {
    // Unknown endpoint
    http_response_code(404);
    echo json_encode([
        'error' => 'Endpoint not found',
        'endpoint' => $endpoint,
        'supported_endpoints' => array_keys($endpoint_routing)
    ]);
    exit;
}

// Construct full Flask URL
$flask_url = $flask_base_url . '/' . $endpoint;

// Add query parameters if present
if (!empty($_SERVER['QUERY_STRING'])) {
    $flask_url .= '?' . $_SERVER['QUERY_STRING'];
}

// Get the request method
$method = $_SERVER['REQUEST_METHOD'];

// Get the request headers
$headers = array();
foreach (getallheaders() as $name => $value) {
    // Forward important headers to Flask
    if (in_array(strtolower($name), ['content-type', 'authorization', 'x-forwarded-for'])) {
        $headers[] = "$name: $value";
    }
}

// Get the request body (for POST requests)
$body = file_get_contents('php://input');

// Initialize cURL
$curl = curl_init();

// Set cURL options
curl_setopt_array($curl, array(
    CURLOPT_URL => $flask_url,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_TIMEOUT => 300,
    CURLOPT_CUSTOMREQUEST => $method,
    CURLOPT_HTTPHEADER => $headers,
    CURLOPT_POSTFIELDS => $body,
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_SSL_VERIFYHOST => false,
    CURLOPT_HEADERFUNCTION => function($curl, $header) {
        // Forward response headers from Flask to client
        $trimmed_header = trim($header);
        if (!empty($trimmed_header) && strpos($trimmed_header, ':') !== false) {
            // Skip certain headers that shouldn't be forwarded
            if (!preg_match('/^(connection|transfer-encoding|content-encoding):/i', $trimmed_header)) {
                header($trimmed_header);
            }
        }
        return strlen($header);
    }
));

// Execute the request
$response = curl_exec($curl);

// Check for errors
if (curl_error($curl)) {
    http_response_code(500);
    echo json_encode([
        'error' => 'Proxy error: ' . curl_error($curl),
        'flask_url' => $flask_url
    ]);
    exit;
}

// Get the HTTP status code
$http_code = curl_getinfo($curl, CURLINFO_HTTP_CODE);
http_response_code($http_code);

// Close cURL
curl_close($curl);

// Output the response
echo $response;
?>