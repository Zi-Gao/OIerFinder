import assert from 'node:assert/strict';
import test from 'node:test';

import SwaggerParser from '@apidevtools/swagger-parser';

import app from './index.js';
import openApiDocument from './openapi.js';

const documentedOperations = () => Object.entries(openApiDocument.paths)
    .flatMap(([path, pathItem]) => Object.keys(pathItem)
        .map(method => `${method.toUpperCase()} ${path}`))
    .sort();

const registeredBusinessOperations = (includeQueryApi = false) => app.routes
    .filter(route => !['/docs', '/openapi.json', '/*'].includes(route.path))
    .filter(route => includeQueryApi || route.path !== '/query-oier')
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
    assert.equal(openApiDocument.paths['/query-oier'], undefined);
    assert.doesNotMatch(openApiDocument.info.description, /独立服务/);
});

test('explicitly enabling the retained query API restores its documented contract', async () => {
    const response = await app.request('/openapi.json', {}, { ENABLE_QUERY_API: 'true' });
    const document = await response.json();
    await SwaggerParser.validate(document);
    const operations = Object.entries(document.paths)
        .flatMap(([path, pathItem]) => Object.keys(pathItem).map(method => `${method.toUpperCase()} ${path}`))
        .sort();
    assert.deepEqual(operations, registeredBusinessOperations(true));
});

test('Scalar API reference is available at /docs', async () => {
    const response = await app.request('/docs');
    const html = await response.text();

    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /^text\/html/);
    assert.match(html, /OIerFinder API/);
    assert.match(html, /\/openapi\.json/);
});
