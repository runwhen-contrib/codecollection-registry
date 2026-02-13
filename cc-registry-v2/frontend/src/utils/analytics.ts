/**
 * Google Analytics Helper Functions
 * Track custom events and page views
 */

declare global {
  interface Window {
    gtag?: (...args: any[]) => void;
  }
}

/**
 * Track a page view (for manual tracking in SPAs)
 */
export const trackPageView = (path: string, title?: string) => {
  if (window.gtag && process.env.REACT_APP_GA_MEASUREMENT_ID) {
    window.gtag('config', process.env.REACT_APP_GA_MEASUREMENT_ID, {
      page_path: path,
      page_title: title,
    });
  }
};

/**
 * Track a custom event
 * @param action - The action name (e.g., 'click', 'search', 'download')
 * @param category - The category (e.g., 'Codebundle', 'Navigation', 'User')
 * @param label - Optional label for more context
 * @param value - Optional numeric value
 */
export const trackEvent = (
  action: string,
  category: string,
  label?: string,
  value?: number
) => {
  if (window.gtag && process.env.REACT_APP_GA_MEASUREMENT_ID) {
    window.gtag('event', action, {
      event_category: category,
      event_label: label,
      value: value,
    });
  }
};

/**
 * Track codebundle views
 */
export const trackCodebundleView = (codebundleSlug: string, collectionSlug: string) => {
  trackEvent('view_codebundle', 'Codebundle', `${collectionSlug}/${codebundleSlug}`);
};

/**
 * Track search queries
 */
export const trackSearch = (query: string, resultsCount: number) => {
  trackEvent('search', 'Search', query, resultsCount);
};

/**
 * Track chat interactions
 */
export const trackChatQuery = (query: string) => {
  trackEvent('chat_query', 'Chat', query.substring(0, 100)); // Limit to 100 chars
};

/**
 * Track codebundle added to cart/config
 */
export const trackAddToCart = (codebundleSlug: string) => {
  trackEvent('add_to_configuration', 'Codebundle', codebundleSlug);
};

/**
 * Track navigation events
 */
export const trackNavigation = (destination: string) => {
  trackEvent('navigate', 'Navigation', destination);
};
