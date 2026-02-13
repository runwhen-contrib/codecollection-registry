import React, { useEffect, useState, useRef } from 'react';
import { Box } from '@mui/material';

interface FlipTextProps {
  text: string;
  duration?: number;
  staggerDelay?: number;
  style?: React.CSSProperties;
}

const FlipText: React.FC<FlipTextProps> = ({ 
  text, 
  duration = 1200, // Slowed down 1.5x (was 800ms)
  staggerDelay = 100, // Slowed down 1.5x (was 70ms)
  style = {}
}) => {
  const [displayText, setDisplayText] = useState(text);
  const [flipping, setFlipping] = useState<Set<number>>(new Set());
  const prevTextRef = useRef(text);

  useEffect(() => {
    if (prevTextRef.current === text) return;

    const oldText = prevTextRef.current;
    const newText = text;
    const maxLength = Math.max(oldText.length, newText.length);
    const charsToFlip = new Set<number>();

    // Find which character positions changed
    for (let i = 0; i < maxLength; i++) {
      if (oldText[i] !== newText[i]) {
        charsToFlip.add(i);
      }
    }

    if (charsToFlip.size === 0) return;

    // Flip characters with stagger effect
    const flipIndices = Array.from(charsToFlip);
    flipIndices.forEach((index, arrayIndex) => {
      setTimeout(() => {
        setFlipping(prev => new Set(prev).add(index));
        
        setTimeout(() => {
          setDisplayText(prevText => {
            const chars = prevText.split('');
            chars[index] = newText[index] || '';
            return chars.join('');
          });
          
          setTimeout(() => {
            setFlipping(prev => {
              const next = new Set(prev);
              next.delete(index);
              return next;
            });
          }, duration / 2);
        }, duration / 2);
      }, arrayIndex * staggerDelay);
    });

    prevTextRef.current = text;
  }, [text, duration, staggerDelay]);

  return (
    <Box 
      component="span" 
      sx={{ 
        display: 'inline-flex',
        whiteSpace: 'nowrap',
        flexWrap: 'nowrap',
        ...style 
      }}
    >
      {displayText.split('').map((char, index) => (
        <Box
          key={index}
          component="span"
          sx={{
            display: 'inline-block',
            position: 'relative',
            minWidth: char === ' ' ? '0.3em' : undefined,
            flexShrink: 0,
            animation: flipping.has(index) ? `flipChar ${duration}ms ease-in-out` : 'none',
            transformStyle: 'preserve-3d',
            '@keyframes flipChar': {
              '0%': {
                transform: 'perspective(400px) rotateX(0deg)',
              },
              '50%': {
                transform: 'perspective(400px) rotateX(90deg)',
                opacity: 0.5,
              },
              '100%': {
                transform: 'perspective(400px) rotateX(0deg)',
              }
            }
          }}
        >
          {char}
        </Box>
      ))}
    </Box>
  );
};

export default FlipText;
