/** Read-only adapter shared by the browser and the standalone query service. */
export function sqliteAdapter(database) {
    return {
        prepare(sql) {
            return {
                bind(...params) {
                    return {
                        async all() {
                            const started = performance.now();
                            const statement = database.prepare(sql);
                            try {
                                statement.bind(params);
                                const results = [];
                                while (statement.step()) results.push(statement.getAsObject());
                                return { results, meta: { duration: performance.now() - started } };
                            } finally {
                                statement.free();
                            }
                        },
                    };
                },
            };
        },
    };
}
