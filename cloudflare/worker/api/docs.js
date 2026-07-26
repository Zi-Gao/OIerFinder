import { Scalar } from '@scalar/hono-api-reference';

import openApiDocument from './openapi.js';

export function registerApiDocs(app) {
    app.get('/openapi.json', (c) => c.json(openApiDocument, 200, {
        'Cache-Control': 'public, max-age=300',
    }));
    app.get('/docs', Scalar({
        pageTitle: 'OIerFinder API',
        url: '/openapi.json',
    }));
}
