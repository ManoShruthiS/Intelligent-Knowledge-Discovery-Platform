import { useEffect, useRef, useState } from 'react';

















export function useSmartAutoScroll({ threshold = 64 } = {}) {
  const containerRef = useRef(null);
  const [stickToBottom, setStickToBottom] = useState(true);
  const [wasResumed, setWasResumed] = useState(false);
  const resumeTimerRef = useRef(null);

  
  const measure = () => {
    const el = containerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.clientHeight - el.scrollTop;
    const isNear = distance <= threshold;
    if (isNear !== stickToBottom) {
      setStickToBottom(isNear);
      if (isNear) {
        setWasResumed(true);
        if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current);
        resumeTimerRef.current = setTimeout(() => setWasResumed(false), 1500);
      }
    }
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener('scroll', measure, { passive: true });
    return () => el.removeEventListener('scroll', measure);
    
  }, []);

  
  
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !stickToBottom) return;
    el.scrollTop = el.scrollHeight;
  });

  const scrollToBottom = (behavior = 'smooth') => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
    setStickToBottom(true);
  };

  return { containerRef, stickToBottom, wasResumed, scrollToBottom };
}
