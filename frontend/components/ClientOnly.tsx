'use client';

import { ReactNode, useEffect, useState } from 'react';

/** Charts measure the DOM, so keep them out of the static prerender pass. */
export function ClientOnly({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return <>{mounted ? children : fallback}</>;
}
