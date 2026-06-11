#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <SoftwareSerial.h>

#define RX_PIN 10
#define TX_PIN 11
SoftwareSerial miBluetooth(RX_PIN, TX_PIN); 

Adafruit_PWMServoDriver servos = Adafruit_PWMServoDriver(0x40);

int pos0 = 102;
int pos180 = 512;

// --- ÁNGULOS ACTUALES (La posición real en este instante) ---
float anguloBase = 90.0;
float anguloBasePrincipal1 = 90.0; 
float anguloBasePrincipal2 = 90.0;
float anguloExt1 = 90.0;
float anguloExt2 = 90.0;
float anguloPinza = 110.0;

// --- ÁNGULOS OBJETIVO (A dónde queremos que llegue) ---
int objBase = 90;
int objBasePrincipal1 = 90;
int objBasePrincipal2 = 90;
int objExt1 = 90;
int objExt2 = 90;
int objPinza = 110;

// VELOCIDAD DE MOVIMIENTO (Menor número = más suave/lento, Mayor número = más rápido)
const float VELOCIDAD = 0.05; 

// Definición de canales en el PCA9685
const int CANAL_BASE = 0;
const int CANAL_B_PRINCIPAL_1 = 3;
const int CANAL_B_PRINCIPAL_2 = 6; 
const int CANAL_EXT1 = 9;
const int CANAL_EXT2 = 12;
const int CANAL_PINZA = 15;

unsigned long ultimoTiempo = 0;

void setup() {
  Serial.begin(9600);
  miBluetooth.begin(9600);
  
  servos.begin();
  servos.setPWMFreq(50);
  
  // Mover inmediatamente a la posición inicial
  actualizarServosFisicos();
  Serial.println("Brazo listo en modo suave. Esperando comandos...");
}

void loop() {
  // 1. LEER COMANDOS BLUETOOTH (Actualizan el OBJETIVO, no el ángulo real)
  if (miBluetooth.available() > 0) {
    char comando = miBluetooth.read();
    Serial.print("Comando recibido: ");
    Serial.println(comando);
    
    switch (comando) {
      // --- Base ---
      case 'A': case 'a': objBase = constrain(objBase + 15, 0, 180); break;
      case 'D': case 'd': objBase = constrain(objBase - 15, 0, 180); break;

      // --- Base Principal ---
      case 'W': case 'w':
        objBasePrincipal1 = constrain(objBasePrincipal1 + 15, 10, 170);
        objBasePrincipal2 = constrain(objBasePrincipal2 - 15, 10, 170);
        break;
      case 'S': case 's':
        objBasePrincipal1 = constrain(objBasePrincipal1 - 15, 10, 170);
        objBasePrincipal2 = constrain(objBasePrincipal2 + 15, 10, 170);
        break;

      // --- Primera Extensión ---
      case 'I': case 'i': objExt1 = constrain(objExt1 - 15, 0, 150); break;
      case 'K': case 'k': objExt1 = constrain(objExt1 + 15, 0, 150); break;

      // --- Segunda Extensión ---
      case 'J': case 'j': objExt2 = constrain(objExt2 - 15, 10, 160); break;
      case 'L': case 'l': objExt2 = constrain(objExt2 + 15, 10, 160); break;

      // --- Pinza ---
      case 'O': case 'o': objPinza = constrain(objPinza - 15, 110, 145); break;
      case 'C': case 'c': objPinza = constrain(objPinza + 15, 110, 145); break;
        
      default: break;
    }
  }

  // 2. CALCULAR INTERPOLACIÓN SUAVE (Se ejecuta continuamente cada 15 milisegundos)
  if (millis() - ultimoTiempo >= 15) {
    ultimoTiempo = millis();
    
    // Aplicamos una fórmula de interpolación lineal (LERP)
    // AnguloActual = AnguloActual + (Objetivo - AnguloActual) * VELOCIDAD
    anguloBase += (objBase - anguloBase) * VELOCIDAD;
    anguloBasePrincipal1 += (objBasePrincipal1 - anguloBasePrincipal1) * VELOCIDAD;
    anguloBasePrincipal2 += (objBasePrincipal2 - anguloBasePrincipal2) * VELOCIDAD;
    anguloExt1 += (objExt1 - anguloExt1) * VELOCIDAD;
    anguloExt2 += (objExt2 - anguloExt2) * VELOCIDAD;
    anguloPinza += (objPinza - anguloPinza) * VELOCIDAD;

    // Enviar los datos calculados a los motores
    actualizarServosFisicos();
  }
}

// Envía las posiciones interpoladas a la placa PCA9685
void actualizarServosFisicos() {
  setServo(CANAL_BASE, (int)anguloBase);
  setServo(CANAL_B_PRINCIPAL_1, (int)anguloBasePrincipal1);
  setServo(CANAL_B_PRINCIPAL_2, (int)anguloBasePrincipal2); 
  setServo(CANAL_EXT1, (int)anguloExt1);
  setServo(CANAL_EXT2, (int)anguloExt2);
  setServo(CANAL_PINZA, (int)anguloPinza);
}

void setServo(uint8_t n_servo, int angulo) {
  int pulse = map(angulo, 0, 180, pos0, pos180);
  servos.setPWM(n_servo, 0, pulse);
}