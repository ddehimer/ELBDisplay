#include <PCA9557.h>
#include <lvgl.h>
#include <Crowbits_DHT20.h>

#include <SPI.h>
#include <Adafruit_GFX.h>
#include "ui/ui.h"
#include "lgfx/lgfx.h"


static lv_obj_t *helloLabel = nullptr;
static lv_style_t style_title;


// Setup the panel.
void setup()
{
  // Three second delay to wait for serial monitor to be running.  Not sure this is necessary going forward
  delay(1000);
  Serial.begin(115200);
  delay(2000);

  Serial.println("Running setup...");

  // Setup the panel
  lcd.setup();

  // Initialize the Square Line UI
  ui_init();

  // Run the LVGL timer handler once to get things started
  lv_timer_handler();

  lv_style_init(&style_title);

  // Text color (blue example)
  lv_style_set_text_color(&style_title, lv_color_hex(0x0000FF));

  // Font size via built-in LVGL font
  lv_style_set_text_font(&style_title, &lv_font_montserrat_22);


  helloLabel = lv_label_create(lv_scr_act());
  lv_obj_add_style(helloLabel, &style_title, 0);
  lv_label_set_text(helloLabel, "ELB Display");
  lv_obj_align(helloLabel, LV_ALIGN_TOP_MID, 0, 10);

}

int clickCount = 0;




// Handle Click event
void clickedClickMe(lv_event_t *e)
{
  clickCount++;
  char ClickBuffer[20];
  snprintf(ClickBuffer, sizeof(ClickBuffer), "%d", clickCount);
  lv_label_set_text(ui_LabelCount, ClickBuffer);
}


// Run Ardunio event loop
void loop()
{
  lv_timer_handler(); /* let the GUI do its work */
  delay(10);
}
