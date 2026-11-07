/**
 * Cloudflare Pages Function: Dynamic Fallback for non-prerendered pharmacies
 * Route: /pharmacie/:slug
 */
export async function onRequest(context) {
  // 1. Delegate to static asset first (all ~18,000 pre-rendered static HTML files)
  const response = await context.next();
  if (response.status === 200) {
    return response;
  }

  // 2. Extract requested slug
  const url = new URL(context.request.url);
  const segments = url.pathname.replace(/^\/pharmacie\/?/, '').replace(/\/+$/, '').split('/');
  const slug = segments[0];
  if (!slug) {
    return response;
  }

  // 3. Resolve department code from slug (e.g. -43110 -> 43, -97400 -> 974, -2A000 -> 2A)
  let deptCode = null;
  const domTomMatch = slug.match(/-(97[1-6])[0-9]{2}(?:-[0-9]+)?$/i);
  if (domTomMatch) {
    deptCode = domTomMatch[1];
  } else {
    const m = slug.match(/-([0-9]{2}|2[aAbB])[0-9]{2,3}(?:-[0-9]+)?$/i);
    if (m) {
      deptCode = m[1].toUpperCase();
    }
  }

  if (!deptCode) {
    return response;
  }

  // 4. Query JSON shard
  let pharmacy = null;
  const checkDepts = (deptCode === '20') ? ['2A', '2B'] : [deptCode];

  for (const d of checkDepts) {
    try {
      const shardUrl = new URL(`/data/shards/${d}.json`, url.origin);
      const res = await context.env.ASSETS.fetch(new Request(shardUrl));
      if (res.status === 200) {
        const phs = await res.json();
        const found = phs.find(p => p.slug === slug);
        if (found) {
          pharmacy = found;
          deptCode = d;
          break;
        }
      }
    } catch (e) {
      // Shard fetch failed, proceed
    }
  }

  if (!pharmacy) {
    // Pharmacy not found in database: return 404 page
    return response;
  }

  // 5. Re-hydrate using a pre-rendered template shell to preserve exact CSS, JS, CMP & Header/Footer
  try {
    const sampleUrl = new URL('/pharmacie/3b-pharma-paris-75012/', url.origin);
    const sampleRes = await context.env.ASSETS.fetch(new Request(sampleUrl));
    if (sampleRes.status === 200) {
      let html = await sampleRes.text();

      const newTitle = `${pharmacy.nom} à ${pharmacy.ville} (${pharmacy.codePostal}) : Téléphone, Avis et Garde`;
      const newDesc = `Consultez les informations de ${pharmacy.nom} à ${pharmacy.ville} (${pharmacy.codePostal}) : téléphone direct ${pharmacy.telephone || '3237'}, avis clients (${pharmacy.googleRating ? pharmacy.googleRating + '★' : 'vérifiés'}), adresse et tour de garde.`;
      const newCanonical = `https://www.pharmaciedegarde24.fr/pharmacie/${pharmacy.slug}/`;

      html = html.replace(/<title>.*?<\/title>/, `<title>${newTitle}</title>`);
      html = html.replace(/<meta name="description" content=".*?">/, `<meta name="description" content="${newDesc}">`);
      html = html.replace(/<link rel="canonical" href=".*?">/, `<link rel="canonical" href="${newCanonical}">`);
      html = html.replace(/<link rel="alternate" hreflang="fr" href=".*?">/, `<link rel="alternate" hreflang="fr" href="${newCanonical}">`);
      html = html.replace(/<meta property="og:title" content=".*?">/, `<meta property="og:title" content="${newTitle}">`);
      html = html.replace(/<meta property="og:description" content=".*?">/, `<meta property="og:description" content="${newDesc}">`);
      html = html.replace(/<meta property="og:url" content=".*?">/, `<meta property="og:url" content="${newCanonical}">`);

      // Replace H1 and address
      html = html.replace(/<h1>.*?<\/h1>/, `<h1>${pharmacy.nom}</h1>`);
      html = html.replace(
        /<p class="pharma-full-address"[^>]*>[\s\S]*?<\/p>/,
        `<p class="pharma-full-address"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/><circle cx="12" cy="9" r="2.5"/></svg><span>${pharmacy.adresse}</span></p>`
      );

      // Replace phone action button
      const telClean = (pharmacy.telephone || '').replace(/\s+/g, '');
      const phoneHtml = telClean 
        ? `<a href="tel:${telClean}" class="btn btn-phone btn-lg" title="Appeler ${pharmacy.nom}"><span>Appeler le ${pharmacy.telephone}</span></a>`
        : `<a href="tel:3237" class="btn btn-phone btn-lg" title="Appeler le 3237"><span>Appeler le 3237 (Garde)</span></a>`;
      html = html.replace(/<a href="tel:[^"]*" class="btn btn-phone btn-lg"[\s\S]*?<\/a>/, phoneHtml);

      // Replace Google Maps direction link
      const mapUrl = (pharmacy.lat && pharmacy.lon)
        ? `https://www.google.com/maps/dir/?api=1&destination=${pharmacy.lat},${pharmacy.lon}`
        : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(pharmacy.nom + ' ' + pharmacy.adresse)}`;
      html = html.replace(/<a href="https:\/\/www\.google\.com\/maps\/dir\/[^"]*" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-lg">/, `<a href="${mapUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-lg">`);

      // Replace FINESS badge
      html = html.replace(/N° FINESS : [^<]*/, `N° FINESS : ${pharmacy.finessId || 'Officiel'}`);

      return new Response(html, {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'public, max-age=3600, s-maxage=86400',
        }
      });
    }
  } catch (err) {
    // Fallback error
  }

  return response;
}
