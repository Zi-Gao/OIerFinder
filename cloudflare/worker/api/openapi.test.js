import assert from 'node:assert/strict';
import test from 'node:test';

import SwaggerParser from '@apidevtools/swagger-parser';

import app from './index.js';
import openApiDocument from './openapi.js';

const documentedOperations = () => Object.entries(openApiDocument.paths)
    .flatMap(([path, pathItem]) => Object.keys(pathItem)
        .map(method => `${method.toUpperCase()} ${path}`))
    .sort();

const registeredBusinessOperations = () => app.routes
    .filter(route => !['/docs', '/openapi.json', '/*'].includes(route.path))
    .map(route => `${route.method} ${route.path}`)
    .sort();

test('OpenAPI document is a valid 3.1 contract for every business API route', async () => {
    await SwaggerParser.validate(openApiDocument);

    assert.equal(openApiDocument.openapi, '3.1.0');
    assert.deepEqual(documentedOperations(), registeredBusinessOperations());
});

test('OpenAPI JSON is served before the SPA fallback', async () => {
    const response = await app.request('/openapi.json');

    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /^application\/json/);
    assert.match(response.headers.get('cache-control'), /max-age=300/);
    assert.deepEqual(await response.json(), openApiDocument);
});

test('Scalar API reference is available at /docs', async () => {
    const response = await app.request('/docs');
    const html = await response.text();

    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /^text\/html/);
    assert.match(html, /OIerFinder API/);
    assert.match(html, /\/openapi\.json/);
});
