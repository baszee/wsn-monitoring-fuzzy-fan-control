/*
 * WSNova Arduino Uno PWM Bridge
 *
 * Board       : Arduino Uno R3 / clone ATmega328P 16 MHz
 * PWM output  : D9 (OC1A / Timer1)
 * Frequency   : 25 kHz
 * Serial      : 115200 baud
 *
 * Aplikasi mengirim duty cycle FAN 0..100%. Karena rangkaian 2N2222
 * open-collector membalik level listrik, nilai itu dikonversi ke duty GPIO
 * (100 - duty fan) di sini. Jangan memberi daya fan 12 V dari Arduino.
 */

#include <Arduino.h>

const uint8_t PWM_PIN = 9;
const uint32_t SERIAL_BAUD = 115200;
const uint16_t TIMER1_TOP = 639;  // 16 MHz / (1 * (639 + 1)) = 25 kHz
const unsigned long COMMAND_TIMEOUT_MS = 15000;  // 15 detik batas timeout failsafe komunikasi

char inputBuffer[48];
uint8_t inputLength = 0;
float currentFanDuty = 0.0f;
bool pwmInverted = true;
unsigned long lastValidCommandAt = 0;

void connectTimerOutput() {
  TCCR1A = (TCCR1A & ~(_BV(COM1A1) | _BV(COM1A0))) | _BV(COM1A1);
}

void disconnectTimerOutput() {
  TCCR1A &= ~(_BV(COM1A1) | _BV(COM1A0));
}

void setElectricalDuty(float percent) {
  percent = constrain(percent, 0.0f, 100.0f);

  // Endpoint dibuat benar-benar LOW/HIGH, bukan pulsa sangat sempit Timer1.
  if (percent <= 0.0f) {
    disconnectTimerOutput();
    digitalWrite(PWM_PIN, LOW);
    return;
  }
  if (percent >= 100.0f) {
    disconnectTimerOutput();
    digitalWrite(PWM_PIN, HIGH);
    return;
  }

  OCR1A = (uint16_t)round((percent / 100.0f) * TIMER1_TOP);
  connectTimerOutput();
}

void setFanDuty(float fanPercent) {
  currentFanDuty = constrain(fanPercent, 0.0f, 100.0f);
  const float electricalDuty = pwmInverted
      ? 100.0f - currentFanDuty
      : currentFanDuty;
  setElectricalDuty(electricalDuty);
}

void printPWM() {
  Serial.print(F("OK PWM "));
  Serial.println(currentFanDuty, 2);
}

void handleCommand(char *command) {
  while (*command == ' ') command++;

  if (strcmp(command, "PING") == 0) {
    lastValidCommandAt = millis();
    Serial.println(F("OK READY"));
    return;
  }

  if (strcmp(command, "STATUS") == 0) {
    lastValidCommandAt = millis();
    printPWM();
    return;
  }

  if (strcmp(command, "INVERTED 0") == 0 || strcmp(command, "INVERTED 1") == 0) {
    pwmInverted = command[9] == '1';
    setFanDuty(currentFanDuty);
    lastValidCommandAt = millis();
    Serial.print(F("OK INVERTED "));
    Serial.println(pwmInverted ? 1 : 0);
    return;
  }

  if (strcmp(command, "STOP") == 0) {
    setFanDuty(0.0f);
    lastValidCommandAt = millis();
    printPWM();
    return;
  }

  if (strncmp(command, "PWM ", 4) == 0) {
    char *endPointer = nullptr;
    const float requested = strtod(command + 4, &endPointer);
    while (endPointer != nullptr && *endPointer == ' ') endPointer++;
    if (endPointer == command + 4 || endPointer == nullptr || *endPointer != '\0' ||
        requested < 0.0f || requested > 100.0f) {
      Serial.println(F("ERR PWM_RANGE"));
      return;
    }
    setFanDuty(requested);
    lastValidCommandAt = millis();
    printPWM();
    return;
  }

  Serial.println(F("ERR UNKNOWN_COMMAND"));
}

void setupTimer1() {
  pinMode(PWM_PIN, OUTPUT);
  digitalWrite(PWM_PIN, HIGH);  // fan duty 0% setelah inversi open-collector

  // Fast PWM mode 14, TOP=ICR1, prescaler 1. Output baru disambungkan oleh
  // setElectricalDuty agar nilai endpoint 0%/100% tetap eksak.
  TCCR1A = _BV(WGM11);
  TCCR1B = _BV(WGM13) | _BV(WGM12) | _BV(CS10);
  ICR1 = TIMER1_TOP;
  OCR1A = TIMER1_TOP;
}

void setup() {
  setupTimer1();
  setFanDuty(0.0f);
  Serial.begin(SERIAL_BAUD);
  Serial.setTimeout(50);
  lastValidCommandAt = millis();
  Serial.println(F("READY PWM 0.00"));
}

void loop() {
  while (Serial.available() > 0) {
    const char value = (char)Serial.read();
    if (value == '\r') continue;
    if (value == '\n') {
      inputBuffer[inputLength] = '\0';
      if (inputLength > 0) handleCommand(inputBuffer);
      inputLength = 0;
      continue;
    }
    if (inputLength < sizeof(inputBuffer) - 1) {
      inputBuffer[inputLength++] = value;
    } else {
      inputLength = 0;
      Serial.println(F("ERR COMMAND_TOO_LONG"));
    }
  }

  // Failsafe komunikasi: kembali ke perintah aplikasi 0%. Perilaku mekanis
  // fan pada 0% tetap harus dicatat karena tiap model fan dapat berbeda.
  if (millis() - lastValidCommandAt > COMMAND_TIMEOUT_MS && currentFanDuty != 0.0f) {
    setFanDuty(0.0f);
  }
}
