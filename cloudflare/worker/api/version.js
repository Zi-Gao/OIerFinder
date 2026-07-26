const FULL_GIT_SHA = /^[0-9a-f]{40}$/i;

const normalizeSha = (value) => (
    typeof value === 'string' && FULL_GIT_SHA.test(value)
        ? value.toLowerCase()
        : null
);

export async function getVersionInfo(env) {
    let activeRelease = null;

    try {
        activeRelease = await env.DB.prepare(`
            SELECT upstream_sha
            FROM DataRelease
            WHERE id = 1 AND status = 'active'
        `).first();
    } catch (error) {
        console.error('Failed to read the active OIerDB data version:', error);
    }

    return {
        oierfinder_sha: normalizeSha(env.OIERFINDER_SHA),
        oierdb_data_sha: normalizeSha(activeRelease?.upstream_sha),
    };
}

export default async function versionHandler(c) {
    const versionInfo = await getVersionInfo(c.env);
    return c.json(versionInfo, 200, {
        'Cache-Control': 'no-store',
    });
}
