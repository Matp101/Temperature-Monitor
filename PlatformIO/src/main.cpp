//=============================================================================
// This Project lets you use a multplexer to read in multiple temperature
// probes. Up to 16 probes will be connected to a multiplexer and it will
// transfer the data through serial within a JSON object. This will be sent
// to the software and decoded. The JSON object that will be sent in the
// following format:
// {probe1: 15, probe2: 17, probe3: 18, ...}
// This probes that will be used within the project is the NTC3950 100k
//============================================================================

#include <Arduino.h>
#include <thermistor.h>
#include <ArduinoJson.h>

#define MULTIPLEX_PINS \
  {                    \
    8, 9, 10, 11       \
  }
#define MULTIPLEX_SIG A0
#define MAX_PROBE_COUNT 16

thermistor therm1(MULTIPLEX_SIG, 1);


bool channel[MAX_PROBE_COUNT] = {1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1};
int probeCount = MAX_PROBE_COUNT;

// Multiplexer pins
int mul_pins[] = MULTIPLEX_PINS;
// Multiplexer signal pin
int muxChannel[MAX_PROBE_COUNT][4] = {
    {0, 0, 0, 0}, // channel 0
    {1, 0, 0, 0}, // channel 1
    {0, 1, 0, 0}, // channel 2
    {1, 1, 0, 0}, // channel 3
    {0, 0, 1, 0}, // channel 4
    {1, 0, 1, 0}, // channel 5
    {0, 1, 1, 0}, // channel 6
    {1, 1, 1, 0}, // channel 7
    {0, 0, 0, 1}, // channel 8
    {1, 0, 0, 1}, // channel 9
    {0, 1, 0, 1}, // channel 10
    {1, 1, 0, 1}, // channel 11
    {0, 0, 1, 1}, // channel 12
    {1, 0, 1, 1}, // channel 13
    {0, 1, 1, 1}, // channel 14
    {1, 1, 1, 1}  // channel 15
};

String input = "";      // Input string from serial
String jsonString = ""; // Output JSON

unsigned long currentChannel = 0;        // current time
unsigned long previousMillis = 0;        // last saved time for each set
unsigned long previousChannelMillis = 0; // last saved time for each channel
const long channelInterval = 50;         // interval to wait after reading a channel
DynamicJsonDocument doc(256);           // Global JsonDocument, adjust the capacity as needed
int refreshRate = 2000; // Refresh rate in ms

double readMux(int channel);
void handleSerial();
double roundTwoDecimals(double number);

void setup()
{
  // Setup Multiplexer
  for (int i = 0; i < 4; i++)
  {
    pinMode(mul_pins[i], OUTPUT);
  }
  // Set multiplexer to channel 0
  for (int i = 0; i < 4; i++)
  {
    digitalWrite(mul_pins[i], LOW);
  }

  Serial.begin(9600);
}

void loop()
{
  // Check if serial is available
  if (Serial.available() > 0)
  {
    handleSerial();
  }

  unsigned long currentMillis = millis();

  // Check if on the last channel
  if (currentChannel < sizeof(muxChannel) / sizeof(muxChannel[0]))
  {
    // Check if time has passed to check for new channel, allows for stabilization
    if (currentMillis - previousChannelMillis >= channelInterval)
    {
      // If channel is enabled
      if (channel[currentChannel] == 1)
      {
        // Read and JSON
        double curtemp = readMux(currentChannel);
        // Round to 2 decimal places
        String key = String(currentChannel);
        doc[key] = roundTwoDecimals(curtemp);
      }
      // Check for next channel in the next loop iteration
      currentChannel++;
      previousChannelMillis = currentMillis;
    }
  }
  else
  {
    // If its on the last channel
    if (currentMillis - previousMillis >= refreshRate)
    {
      // Serialize JSON and send
      serializeJson(doc, jsonString);
      Serial.println(jsonString);
      //  Reset for the next cycle
      currentChannel = 0;
      jsonString = "";
      doc.clear(); // Clear JSON document
      previousMillis = currentMillis;
    }
  }
}

void handleSerial()
{
  while (Serial.available() > 0)
  {
    char receivedChar = Serial.read();
    input += receivedChar;

    // Check if we received a newline or carriage return (end of message)
    if (receivedChar == '\n' || receivedChar == '\r')
    {
      StaticJsonDocument<256> doc;
      DeserializationError error = deserializeJson(doc, input);
      if (error)
      {
        Serial.print("ERROR: deserializeJson() failed: ");
        Serial.println(error.c_str());
      }
      else
      {
        probeCount = 0;
        // Setting the refresh rate
        if (doc.containsKey("rr"))
        {
          refreshRate = doc["rr"].as<int>();
        }

        // Setting the channel states
        for (int i = 0; i < MAX_PROBE_COUNT; i++)
        {
          String key = String(i);
          if (doc.containsKey(key))
          {
            channel[i] = doc[key].as<bool>() ? 1 : 0;
            // if its enabled, add to the probe count
            if (channel[i] == 1)
            {
              probeCount++;
            }
          }
        }
      }

      // Clear the input string for the next message
      input = "";
    }
  }
}

double readMux(int channel)
{
  // loop through the 4 sig
  for (int i = 0; i < 4; i++)
  {
    digitalWrite(mul_pins[i], muxChannel[channel][i]);
  }

  double temp = therm1.analog2temp(); // read temperature

  return temp;
}

double roundTwoDecimals(double number) {
    return round(number * 100) / 100.0;
}