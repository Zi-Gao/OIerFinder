const adminSecurity = [
    {},
    { AdminSecret: [] },
];

const errorResponses = {
    400: {
        description: '请求参数或请求体不合法。',
        content: {
            'application/json': {
                schema: { $ref: '#/components/schemas/ErrorResponse' },
            },
        },
    },
    500: {
        description: '服务内部错误。管理员请求可能额外返回调试信息。',
        content: {
            'application/json': {
                schema: { $ref: '#/components/schemas/ErrorResponse' },
            },
        },
    },
};

export const openApiDocument = {
    openapi: '3.1.0',
    info: {
        title: 'OIerFinder API',
        version: '1.0.0',
        description: [
            'OIerFinder Cloudflare Worker 的公开 HTTP API。',
            '',
            '所有接口都可匿名调用。可选的 `X-Admin-Secret` 仅用于提高查询限制并在错误响应中返回调试信息；不要在公开客户端中保存该密钥。',
            '',
            '洛谷接口在 `sync=true` 或 `sync=1` 时会从洛谷读取最新奖项，并在后台增量写入 D1。历史奖项不会因为上游缺失而删除。',
        ].join('\n'),
    },
    servers: [
        {
            url: '/',
            description: '当前部署',
        },
    ],
    tags: [
        {
            name: 'OIer 查询',
            description: '按获奖记录和选手属性筛选 OIer。',
        },
        {
            name: '洛谷同步',
            description: '查询或同步公开的洛谷奖项数据。',
        },
        {
            name: '版本',
            description: '查看当前应用与上游数据版本。',
        },
    ],
    paths: {
        '/query-oier': {
            post: {
                tags: ['OIer 查询'],
                operationId: 'queryOiers',
                summary: '筛选 OIer',
                description: [
                    '`record_filters` 中的每一项都必须被同一名选手的至少一条获奖记录满足，各项之间为 AND 关系。',
                    '普通请求最多使用 20 个记录过滤器，并且必须达到最低查询强度；管理员请求不受这两项限制。',
                    '返回数量向下取整并限制为最多 100 条。',
                ].join('\n\n'),
                security: adminSecurity,
                requestBody: {
                    required: true,
                    content: {
                        'application/json': {
                            schema: {
                                $ref: '#/components/schemas/QueryOierRequest',
                            },
                            examples: {
                                noiGold: {
                                    summary: '查询 2023 年 NOI 金牌选手',
                                    value: {
                                        record_filters: [
                                            {
                                                contest_type: 'NOI',
                                                level: '金牌',
                                                year: 2023,
                                            },
                                        ],
                                        oier_filters: {},
                                        limit: 20,
                                    },
                                },
                                multipleRecords: {
                                    summary: '组合多个获奖条件',
                                    value: {
                                        record_filters: [
                                            {
                                                contest_type: 'NOI',
                                                level: '金牌',
                                                year: 2023,
                                            },
                                            {
                                                contest_type: 'NOIP提高',
                                                level: '一等奖',
                                                year: 2021,
                                            },
                                        ],
                                        oier_filters: {
                                            enroll_min: 2019,
                                            enroll_max: 2022,
                                        },
                                        limit: 50,
                                    },
                                },
                            },
                        },
                    },
                },
                responses: {
                    200: {
                        description: '查询成功。',
                        content: {
                            'application/json': {
                                schema: {
                                    $ref: '#/components/schemas/QueryOierResponse',
                                },
                            },
                        },
                    },
                    ...errorResponses,
                },
            },
        },
        '/luogu/to_query': {
            get: {
                tags: ['洛谷同步'],
                operationId: 'getQueryFromLuogu',
                summary: '把洛谷奖项转换成 OIerFinder 查询条件',
                description: [
                    '读取指定洛谷用户的奖项，并把可识别的 NOI 系列奖项转换为 `record_filters`。',
                    '设置 `sync=true` 或 `sync=1` 会先请求洛谷，并在响应返回后通过后台任务增量写入 D1。',
                ].join('\n\n'),
                security: adminSecurity,
                parameters: [
                    { $ref: '#/components/parameters/LuoguUid' },
                    { $ref: '#/components/parameters/Sync' },
                ],
                responses: {
                    200: {
                        description: '转换成功。同步失败时仍返回已有 D1 数据，并设置 `synced=false` 和 `sync_error`。',
                        content: {
                            'application/json': {
                                schema: {
                                    $ref: '#/components/schemas/LuoguQueryResponse',
                                },
                            },
                        },
                    },
                    ...errorResponses,
                },
            },
        },
        '/luogu/prizes': {
            get: {
                tags: ['洛谷同步'],
                operationId: 'getLuoguPrizes',
                summary: '查询洛谷奖项',
                description: [
                    '返回指定洛谷用户已经保存的奖项以及可用于 `/query-oier` 的查询条件。',
                    '设置 `sync=true` 或 `sync=1` 会请求洛谷，并在响应返回后通过后台任务增量写入 D1。该同步是公开写操作，历史奖项不会删除。',
                ].join('\n\n'),
                security: adminSecurity,
                parameters: [
                    { $ref: '#/components/parameters/LuoguUid' },
                    { $ref: '#/components/parameters/Sync' },
                    {
                        name: 'noi_only',
                        in: 'query',
                        required: false,
                        description: '为 `true` 或 `1` 时，`prizes` 只返回 NOI 系列奖项。生成的 `query_payload` 始终只使用 NOI 系列奖项。',
                        schema: {
                            type: 'boolean',
                            default: false,
                        },
                    },
                ],
                responses: {
                    200: {
                        description: '查询成功。同步失败时仍返回已有 D1 数据，并设置 `synced=false` 和 `sync_error`。',
                        content: {
                            'application/json': {
                                schema: {
                                    $ref: '#/components/schemas/LuoguPrizesResponse',
                                },
                            },
                        },
                    },
                    ...errorResponses,
                },
            },
        },
        '/version': {
            get: {
                tags: ['版本'],
                operationId: 'getVersion',
                summary: '获取当前版本',
                description: '返回当前部署的 OIerFinder Git SHA，以及 D1 中 active 数据发布对应的 OIerDB Data Git SHA。开发环境或数据尚未发布时字段可能为 `null`。',
                responses: {
                    200: {
                        description: '获取成功。',
                        content: {
                            'application/json': {
                                schema: {
                                    $ref: '#/components/schemas/VersionResponse',
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    components: {
        securitySchemes: {
            AdminSecret: {
                type: 'apiKey',
                in: 'header',
                name: 'X-Admin-Secret',
                description: '可选管理员密钥。用于放宽 `/query-oier` 的部分资源限制，并在 500 响应中附加调试信息。',
            },
        },
        parameters: {
            LuoguUid: {
                name: 'uid',
                in: 'query',
                required: true,
                description: '洛谷用户数字 UID。',
                schema: {
                    type: 'integer',
                    minimum: 1,
                },
                example: 1,
            },
            Sync: {
                name: 'sync',
                in: 'query',
                required: false,
                description: '为 `true` 或 `1` 时从洛谷刷新数据，并在后台增量写入 D1。',
                schema: {
                    type: 'boolean',
                    default: false,
                },
            },
        },
        schemas: {
            ErrorResponse: {
                type: 'object',
                additionalProperties: false,
                required: ['error'],
                properties: {
                    error: {
                        type: 'string',
                        description: '适合展示给调用方的错误消息。',
                    },
                    details: {
                        type: 'string',
                        description: '仅管理员请求可能返回的内部错误详情。',
                    },
                    stack: {
                        type: 'string',
                        description: '仅管理员请求可能返回的调用栈。',
                    },
                },
            },
            RecordFilter: {
                type: 'object',
                additionalProperties: false,
                description: '单组获奖记录条件。每个单数字段和对应的复数字段不能同时提供。',
                properties: {
                    level: {
                        type: 'string',
                        minLength: 1,
                        description: '单个奖项等级；不能与 `levels` 同时提供。',
                        example: '金牌',
                    },
                    levels: {
                        type: 'array',
                        uniqueItems: true,
                        items: { type: 'string', minLength: 1 },
                        description: '多个可接受的奖项等级；不能与 `level` 同时提供。',
                    },
                    min_score: {
                        type: 'number',
                        description: '最低分数，包含边界。',
                    },
                    max_score: {
                        type: 'number',
                        description: '最高分数，包含边界。',
                    },
                    min_rank: {
                        type: 'number',
                        description: '最小名次数值，包含边界。',
                    },
                    max_rank: {
                        type: 'number',
                        description: '最大名次数值，包含边界。',
                    },
                    province: {
                        type: 'string',
                        minLength: 1,
                        description: '单个参赛省份；不能与 `provinces` 同时提供。',
                        example: '北京',
                    },
                    provinces: {
                        type: 'array',
                        uniqueItems: true,
                        items: { type: 'string', minLength: 1 },
                        description: '多个可接受的参赛省份；不能与 `province` 同时提供。',
                    },
                    school_id: {
                        type: 'integer',
                        description: '单个学校 ID；不能与 `school_ids` 同时提供。',
                    },
                    school_ids: {
                        type: 'array',
                        uniqueItems: true,
                        items: { type: 'integer' },
                        description: '多个可接受的学校 ID；不能与 `school_id` 同时提供。',
                    },
                    contest_id: {
                        type: 'integer',
                        description: '单个比赛 ID；不能与 `contest_ids` 同时提供。',
                    },
                    contest_ids: {
                        type: 'array',
                        uniqueItems: true,
                        items: { type: 'integer' },
                        description: '多个可接受的比赛 ID；不能与 `contest_id` 同时提供。',
                    },
                    year: {
                        type: ['integer', 'null'],
                        description: '单个比赛年份；不能与 `years` 同时提供。`null` 与省略效果相同。',
                        example: 2023,
                    },
                    years: {
                        type: 'array',
                        uniqueItems: true,
                        items: { type: 'integer' },
                        description: '多个可接受的比赛年份；不能与 `year` 同时提供。',
                    },
                    year_start: {
                        type: 'integer',
                        description: '比赛年份下界，包含边界。',
                    },
                    year_end: {
                        type: 'integer',
                        description: '比赛年份上界，包含边界。',
                    },
                    fall_semester: {
                        type: 'boolean',
                        description: '`true` 表示下半年比赛，`false` 表示上半年比赛。',
                    },
                    contest_type: {
                        type: 'string',
                        minLength: 1,
                        description: '单个比赛类型；不能与 `contest_types` 同时提供。',
                        examples: ['NOI', 'NOIP提高', 'CSP提高'],
                    },
                    contest_types: {
                        type: 'array',
                        uniqueItems: true,
                        items: { type: 'string', minLength: 1 },
                        description: '多个可接受的比赛类型；不能与 `contest_type` 同时提供。',
                    },
                },
            },
            OierFilter: {
                type: 'object',
                additionalProperties: false,
                description: '选手本身的属性条件。`gender` 与 `genders` 不能同时提供。',
                properties: {
                    gender: {
                        type: 'string',
                        enum: ['1', '-1'],
                        description: '单个性别编码：`1` 为男，`-1` 为女。',
                    },
                    genders: {
                        type: 'array',
                        uniqueItems: true,
                        items: {
                            type: 'string',
                            enum: ['1', '-1'],
                        },
                        description: '多个可接受的性别编码。',
                    },
                    enroll_min: {
                        type: 'integer',
                        description: '初中入学年份下界，包含边界。',
                    },
                    enroll_max: {
                        type: 'integer',
                        description: '初中入学年份上界，包含边界。',
                    },
                    initials: {
                        type: 'array',
                        uniqueItems: true,
                        items: { type: 'string', minLength: 1 },
                        description: '姓名首字母缩写的精确匹配列表。',
                        example: ['QZH', 'DMY'],
                    },
                },
            },
            QueryOierRequest: {
                type: 'object',
                properties: {
                    record_filters: {
                        type: 'array',
                        items: { $ref: '#/components/schemas/RecordFilter' },
                        default: [],
                        description: '普通请求最多 20 项。每一项必须分别命中同一名选手的一条记录。',
                    },
                    oier_filters: {
                        $ref: '#/components/schemas/OierFilter',
                    },
                    limit: {
                        type: 'integer',
                        minimum: 1,
                        maximum: 100,
                        default: 100,
                        description: '最多返回多少名选手。',
                    },
                },
            },
            Oier: {
                type: 'object',
                additionalProperties: false,
                required: [
                    'uid',
                    'initials',
                    'name',
                    'gender',
                    'enroll_middle',
                    'oierdb_score',
                    'ccf_score',
                    'ccf_level',
                ],
                properties: {
                    uid: { type: 'integer' },
                    initials: { type: ['string', 'null'] },
                    name: { type: 'string' },
                    gender: {
                        type: 'integer',
                        description: '`1` 为男，`-1` 为女。',
                    },
                    enroll_middle: { type: 'integer' },
                    oierdb_score: { type: 'number' },
                    ccf_score: { type: 'number' },
                    ccf_level: { type: 'integer' },
                },
            },
            UsageStep: {
                type: 'object',
                additionalProperties: false,
                required: ['name', 'rows_read', 'rows_written', 'duration_ms'],
                properties: {
                    name: { type: 'string' },
                    rows_read: { type: 'integer', minimum: 0 },
                    rows_written: { type: 'integer', minimum: 0 },
                    duration_ms: { type: 'number', minimum: 0 },
                },
            },
            QueryUsage: {
                type: 'object',
                additionalProperties: false,
                required: ['steps', 'total_rows_read', 'total_rows_written'],
                properties: {
                    steps: {
                        type: 'array',
                        items: { $ref: '#/components/schemas/UsageStep' },
                    },
                    total_rows_read: { type: 'integer', minimum: 0 },
                    total_rows_written: { type: 'integer', minimum: 0 },
                },
            },
            QueryOierResponse: {
                type: 'object',
                additionalProperties: false,
                required: ['data'],
                properties: {
                    data: {
                        type: 'array',
                        items: { $ref: '#/components/schemas/Oier' },
                    },
                    usage: {
                        $ref: '#/components/schemas/QueryUsage',
                        description: '仅提供正确 `X-Admin-Secret` 时返回。',
                    },
                },
            },
            LuoguPrize: {
                type: 'object',
                additionalProperties: false,
                required: [
                    'luogu_uid',
                    'contest_name',
                    'prize_level',
                    'year',
                    'score',
                    'rank',
                    'event',
                    'is_noi_series',
                ],
                properties: {
                    id: {
                        type: 'integer',
                        description: 'D1 中已保存奖项的内部 ID；刚从洛谷获取但尚未写入的奖项可能没有此字段。',
                    },
                    luogu_uid: { type: 'integer' },
                    contest_name: { type: 'string' },
                    prize_level: { type: 'string' },
                    year: { type: ['integer', 'null'] },
                    score: { type: ['number', 'null'] },
                    rank: { type: ['integer', 'null'] },
                    event: { type: ['string', 'null'] },
                    is_noi_series: {
                        oneOf: [
                            { type: 'boolean' },
                            { type: 'integer', enum: [0, 1] },
                        ],
                        description: '是否属于 NOI 系列。D1 中已有记录可能以 `0` 或 `1` 返回。',
                    },
                },
            },
            GeneratedQueryPayload: {
                type: 'object',
                required: ['record_filters', 'oier_filters'],
                properties: {
                    record_filters: {
                        type: 'array',
                        items: { $ref: '#/components/schemas/RecordFilter' },
                    },
                    oier_filters: {
                        $ref: '#/components/schemas/OierFilter',
                    },
                },
            },
            SyncResult: {
                type: 'object',
                required: ['synced'],
                properties: {
                    synced: {
                        type: 'boolean',
                        description: '本次请求是否成功从洛谷读取数据。未要求同步时为 `false`。',
                    },
                    sync_error: {
                        type: 'string',
                        description: '请求洛谷失败时的错误信息；其他情况下省略。',
                    },
                },
            },
            LuoguQueryResponse: {
                allOf: [
                    { $ref: '#/components/schemas/GeneratedQueryPayload' },
                    { $ref: '#/components/schemas/SyncResult' },
                ],
            },
            LuoguPrizesResponse: {
                allOf: [
                    { $ref: '#/components/schemas/SyncResult' },
                    {
                        type: 'object',
                        required: ['prizes', 'query_payload'],
                        properties: {
                            prizes: {
                                type: 'array',
                                items: { $ref: '#/components/schemas/LuoguPrize' },
                            },
                            query_payload: {
                                $ref: '#/components/schemas/GeneratedQueryPayload',
                            },
                        },
                    },
                ],
            },
            VersionResponse: {
                type: 'object',
                additionalProperties: false,
                required: ['oierfinder_sha', 'oierdb_data_sha'],
                properties: {
                    oierfinder_sha: {
                        type: ['string', 'null'],
                        pattern: '^[0-9a-f]{40}$',
                        description: '当前 Worker 对应的 OIerFinder Git SHA。',
                    },
                    oierdb_data_sha: {
                        type: ['string', 'null'],
                        pattern: '^[0-9a-f]{40}$',
                        description: 'D1 active 数据发布对应的 OIerDB Data Git SHA。',
                    },
                },
            },
        },
    },
};

export default openApiDocument;
