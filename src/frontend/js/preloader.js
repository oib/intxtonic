/**
 * Preloader module to prevent flash of unstyled content (FOUC)
 * Shows loading spinner until all stylesheets are loaded
 */

class Preloader {
  constructor() {
    this.stylesheetsLoaded = false;
    this.minDisplayTime = 300; // Minimum time to show preloader
    this.startTime = Date.now();
  }

  init() {
    // Add preloader to DOM
    this.addPreloaderToDOM();
    
    // Make body visible and show preloader
    document.body.classList.add('preloader-ready');
    
    // Check if stylesheets are already loaded
    if (document.readyState === 'complete') {
      this.onStylesheetsLoaded();
    } else {
      this.waitForStylesheets();
    }
    
    // Fallback timeout in case stylesheets take too long
    setTimeout(() => {
      if (!this.stylesheetsLoaded) {
        this.onStylesheetsLoaded();
      }
    }, 3000);
  }

  addPreloaderToDOM() {
    const preloaderHTML = `
      <div class="preloader" id="preloader">
        <div class="preloader__content">
          <div class="preloader__spinner"></div>
          <div class="preloader__text">Loading...</div>
        </div>
      </div>
    `;
    
    // Insert at the beginning of body
    document.body.insertAdjacentHTML('afterbegin', preloaderHTML);
  }

  waitForStylesheets() {
    // Check all stylesheets
    const stylesheets = Array.from(document.styleSheets);
    let loadedCount = 0;
    
    const checkSheet = (sheet) => {
      try {
        // Try to access a rule to see if stylesheet is loaded
        if (sheet.cssRules || sheet.rules) {
          loadedCount++;
          if (loadedCount === stylesheets.length) {
            this.onStylesheetsLoaded();
          }
        }
      } catch (e) {
        // Cross-origin stylesheet, assume it's loaded
        loadedCount++;
        if (loadedCount === stylesheets.length) {
          this.onStylesheetsLoaded();
        }
      }
    };

    if (stylesheets.length === 0) {
      this.onStylesheetsLoaded();
      return;
    }

    stylesheets.forEach(checkSheet);

    // Also check for link elements with rel="stylesheet"
    const linkElements = document.querySelectorAll('link[rel="stylesheet"]');
    linkElements.forEach(link => {
      if (link.sheet) {
        checkSheet(link.sheet);
      } else {
        link.addEventListener('load', () => checkSheet(link.sheet));
        link.addEventListener('error', () => checkSheet(link.sheet));
      }
    });
  }

  onStylesheetsLoaded() {
    if (this.stylesheetsLoaded) return;
    
    this.stylesheetsLoaded = true;
    
    // Ensure minimum display time
    const elapsed = Date.now() - this.startTime;
    const remainingTime = Math.max(0, this.minDisplayTime - elapsed);
    
    setTimeout(() => {
      this.hidePreloader();
    }, remainingTime);
  }

  hidePreloader() {
    const preloader = document.getElementById('preloader');
    if (preloader) {
      preloader.classList.add('preloader--hidden');
      document.body.classList.add('styles-loaded');
      
      // Remove preloader after transition
      setTimeout(() => {
        preloader.remove();
      }, 300);
    }
  }
}

// Initialize preloader
const preloader = new Preloader();

// Export for use in other modules
export { preloader };
export default preloader;
