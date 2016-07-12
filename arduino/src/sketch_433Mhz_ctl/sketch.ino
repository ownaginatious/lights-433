#include <RCSwitch.h>

RCSwitch inputLine = RCSwitch();
RCSwitch outputLine = RCSwitch();

#define PROTOCOL_HEADER "CLS" // (C)LUSTER (L)IGHT (S)WITCH
#define PROTOCOL_VERSION '0'

// input messages
#define READ_433  '1' // <2-byte: message_num><2-byte: radio_timeout>
#define WRITE_433 '2' // <2-byte: protocol><2-byte: delay><2-byte: repetitions>
                      // <2-byte: byte-length><#-bytes: message>

// output messages
#define AWAITING_DATA    'B'
#define INCOMING_DATA    'C'
#define RADIO_TIMEOUT    'D'
#define HELLO            'E'
#define GOODBYE          'F'
#define BAD_HEADER       'G'
#define WRONG_VERSION    'H'
#define HEARTBEAT        'I'
#define UNKNOWN_OP_CODE  'Z'

#define RADIO_POLL_RATE  10 // milliseconds

void setup() {
    Serial.begin(9600);
    Serial.setTimeout(1000);
    inputLine.enableReceive(0);
    outputLine.enableTransmit(4);
    outputLine.setRepeatTransmit(1);
}

unsigned int readShort(){
    unsigned int val = 0x00;
    byte buffer[2]; 
    Serial.readBytes(buffer, 2);
    val = buffer[1];
    val <<= 8;
    val |= buffer[0];
    return val;
}

unsigned long readMessage(int byteLength){
    byte buffer[byteLength];
    Serial.readBytes(buffer, byteLength);
    unsigned long val = buffer[byteLength - 1];
    for (int i = 1; i < byteLength; i++){
        val <<= 8;
        val &= 0xFFFFFF00;
        val |= buffer[byteLength - 1 - i];
    }
    return val;
}

char readChar(){
    return (char) readMessage(1);
}

void writeShort(unsigned int val){
    Serial.write(val & 0xFF);
    val >>= 8;
    Serial.write(val & 0xFF);
}

void loop() { 
    
    if (Serial.available() == 0) {
        return;
    }
    
    // Get the protocol indicator signal
    char receivedHeader[4];
    receivedHeader[3] = '\0';
    Serial.readBytes(receivedHeader, 3);

    if (strcmp(receivedHeader, PROTOCOL_HEADER) != 0){
        Serial.write(BAD_HEADER);
        return;
    }

    char receivedVersion = readChar();

    if (receivedVersion != PROTOCOL_VERSION) {
        Serial.write(WRONG_VERSION);
        return;
    }

    // Acknowledge the correct handshake.
    Serial.write(HELLO);

    // Wait for instruction.
    char inst = readChar();

    // Instruction variables.
    int messageNum, radioTimeout, timeoutCount;
    unsigned int repetitions, messageLength;
    unsigned long message;
    
    switch (inst) {
        case READ_433:
        
            Serial.write(AWAITING_DATA);

            messageNum = readShort();
            radioTimeout = readShort(); // milliseconds

            for (int i = 0; i < messageNum; i++){
                
                timeoutCount = radioTimeout; 

                // Wait for the radio to pick something up.
                while (!inputLine.available()) {
                    if (timeoutCount <= 0){
                        Serial.write(RADIO_TIMEOUT);
                        return;
                    }
                    delay(RADIO_POLL_RATE);
                    timeoutCount -= RADIO_POLL_RATE;
                    if (timeoutCount % 100 == 0) {
                        Serial.write(HEARTBEAT);
                    }
                }
                Serial.write(INCOMING_DATA);

                writeShort(inputLine.getReceivedProtocol());
                writeShort(inputLine.getReceivedDelay());

                // Calculate and send the byte length.
                messageLength = inputLine.getReceivedBitlength();
                // Convert to bytes
                messageLength = messageLength / 8 + (messageLength % 8 > 0 ? 1 : 0);
                writeShort(messageLength);
                message = inputLine.getReceivedValue();
                for (int j = 0; j < messageLength; j++){
                    Serial.write(message & 0xFF);
                    message >>= 8;
                }
                inputLine.resetAvailable();
            }
            
            break;

        case WRITE_433:

            Serial.write(AWAITING_DATA);

            // Read and set the sending parameters.
            outputLine.setProtocol(readShort());
            outputLine.setPulseLength(readShort());
            outputLine.setRepeatTransmit(readShort());

            // Read the message payload.
            messageLength = readShort();
            message = readMessage(messageLength);
            outputLine.send(message, messageLength * 8);
            
            break;

        default:
            Serial.write(UNKNOWN_OP_CODE);
    }

    Serial.write(GOODBYE);
}
