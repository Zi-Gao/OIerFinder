import { Scalar } from '@scalar/hono-api-reference';

import { getOpenApiDocument } from './openapi.js';

export function registerApiDocs(app) {
    app.get('/openapi.json', (c) => c.json(getOpenApiDocument(c.env), 200, {
        'Cache-Control': 'public, max-age=300',
    }));
    app.get('/docs', Scalar({
        pageTitle: 'OIerFinder API',
        url: '/openapi.json',
    }));
}
